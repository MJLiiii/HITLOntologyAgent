package org.oe.studio;

import com.google.gson.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

final class Manifest {
    static final int MAX_BYTES = 1_048_576;
    final Path directory;
    final JsonObject json;
    final Map<String, String> contents = new HashMap<>();

    Manifest(Path path) throws Exception {
        if (Files.isSymbolicLink(path) || Files.size(path) > MAX_BYTES) throw new IllegalArgumentException("Invalid manifest file");
        directory = path.toRealPath().getParent();
        json = JsonParser.parseString(Files.readString(path)).getAsJsonObject();
        if (json.get("schema_version").getAsInt() != 1 || !text(json, "expected_runner_version").equals(Runner.VERSION))
            throw new IllegalArgumentException("Unsupported manifest/runner version");
        if (!text(json, "inference_mode").equals("rdfs") || !text(json, "validation_graph").equals("asserted_plus_inferred"))
            throw new UnsupportedOperationException("Only rdfs asserted_plus_inferred is supported");
        if (!text(json, "bundle_digest").matches("(?:sha256:)?[a-f0-9]{64}")) throw new IllegalArgumentException("Invalid bundle digest");
        JsonObject artifacts = json.getAsJsonObject("artifacts");
        for (var entry : artifacts.entrySet()) {
            if (!Set.of("ontology", "shapes", "fixtures", "tests", "profile").contains(entry.getKey()))
                throw new UnsupportedOperationException("Unrecognized artifact: " + entry.getKey());
            JsonObject artifact = entry.getValue().getAsJsonObject();
            String name = text(artifact, "path");
            if (!name.matches("[A-Za-z0-9_.-]+") || name.equals(".") || name.equals(".."))
                throw new IllegalArgumentException("Artifact must be a local filename");
            Path file = directory.resolve(name);
            if (Files.isSymbolicLink(file) || !file.toRealPath().getParent().equals(directory) || Files.size(file) > MAX_BYTES)
                throw new IllegalArgumentException("Artifact path or size rejected");
            byte[] bytes = Files.readAllBytes(file);
            if (!sha256(bytes).equals(text(artifact, "sha256"))) throw new IllegalArgumentException("Artifact hash mismatch: " + entry.getKey());
            contents.put(entry.getKey(), new String(bytes, StandardCharsets.UTF_8));
        }
        if (!contents.keySet().containsAll(Set.of("ontology", "shapes", "fixtures", "tests", "profile")))
            throw new IllegalArgumentException("Missing required manifest artifacts");
    }

    static String text(JsonObject object, String key) { return object.get(key).getAsString(); }
    static String sha256(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
}
