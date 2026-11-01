package org.oe.studio;

import com.google.gson.*;
import org.apache.jena.query.*;
import org.apache.jena.rdf.model.*;
import org.apache.jena.reasoner.ReasonerRegistry;
import org.apache.jena.riot.*;
import org.apache.jena.riot.out.NodeFmtLib;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;

/** A local manifest protocol, deliberately not an upstream Jena command line. */
public final class Runner {
    static final String VERSION = "0.1.0";
    static final Gson JSON = new GsonBuilder().setPrettyPrinting().disableHtmlEscaping().create();
    final JsonObject report = new JsonObject();
    final JsonArray stages = new JsonArray(), cases = new JsonArray();
    final Model rawShacl = ModelFactory.createDefaultModel();
    Path directory;

    public static void main(String[] args) {
        if (args.length != 2 || !args[0].equals("--manifest")) { System.err.println("Usage: java -jar oe-jena-runner.jar --manifest <manifest.json>"); System.exit(3); }
        Runner runner = new Runner();
        int code = runner.execute(Path.of(args[1]).toAbsolutePath());
        System.exit(code);
    }

    int execute(Path path) {
        directory = path.getParent();
        report.addProperty("id", UUID.randomUUID().toString());
        report.addProperty("started_at", Instant.now().toString());
        report.addProperty("profile", "rdfs");
        report.addProperty("validation_graph", "asserted_plus_inferred");
        JsonObject engine = new JsonObject(); engine.addProperty("name", "Apache Jena"); engine.addProperty("version", libraryVersion()); engine.addProperty("runner_version", VERSION); report.add("engine", engine);
        report.add("stages", stages); report.add("cases", cases); report.add("limitations", new JsonArray());
        int exit;
        try {
            Manifest manifest = new Manifest(path);
            report.addProperty("bundle_digest", Manifest.text(manifest.json, "bundle_digest"));
            Model ontology = parse(manifest.contents.get("ontology"));
            Model shapes = parse(manifest.contents.get("shapes"));
            Model fixture = parse(manifest.contents.get("fixtures"));
            JsonArray specs = JsonParser.parseString(manifest.contents.get("tests")).getAsJsonArray();
            if (specs.size() > 100) throw new IllegalArgumentException("Test case limit exceeded");
            Profile profile = new Profile(JsonParser.parseString(manifest.contents.get("profile")).getAsJsonObject(), ontology);
            report.add("limitations", profile.limitations);
            profile.check(ontology, false); profile.check(fixture, true); Profile.checkShapes(shapes);
            Map<String, Query> queries = new HashMap<>();
            Set<String> ids = new HashSet<>();
            // Parse and inspect every case before any query or constraint evaluation.
            for (JsonElement element : specs) {
                JsonObject spec = element.getAsJsonObject();
                String id = id(spec), kind = Manifest.text(spec, "kind");
                if (id.isBlank() || !ids.add(id)) throw new IllegalArgumentException("Missing or duplicate case ID");
                if (spec.has("inference_mode") && !Manifest.text(spec, "inference_mode").equals("rdfs")) throw new UnsupportedOperationException("Test inference profile differs from runner");
                if (spec.has("fixtures_ttl")) profile.check(parse(Manifest.text(spec, "fixtures_ttl")), true);
                if (kind.equals("ask") || kind.equals("select_rows")) queries.put(id, QueryStage.parse(spec));
                else if (kind.equals("shacl")) {
                    if (!spec.has("expected_conforms") || !spec.get("expected_conforms").isJsonPrimitive() || !spec.getAsJsonPrimitive("expected_conforms").isBoolean())
                        throw new IllegalArgumentException("SHACL case requires explicit expected_conforms boolean");
                } else throw new UnsupportedOperationException("Unsupported test kind: " + kind);
            }
            stage("integrity_and_syntax", "passed", "All artifact hashes, RDF inputs and test schemas checked");
            stage("admitted_profile", "passed", "Restricted named-triple RDFS profile; local SHACL Core and SPARQL algebra inspected");
            Model asserted = ModelFactory.createDefaultModel().add(ontology).add(fixture);
            Model closure = infer(asserted);
            JsonObject metrics = new JsonObject(); metrics.addProperty("asserted_triples", asserted.size()); metrics.addProperty("closure_triples", closure.size()); metrics.addProperty("inferred_triples", closure.size() - asserted.size());
            report.add("metrics", metrics); report.addProperty("asserted_graph_sha256", hash(asserted)); report.addProperty("inferred_graph_sha256", hash(closure));
            stage("materialization", "passed", "Apache Jena RDFS closure materialized");
            JsonObject constraints = ShaclStage.run(shapes, closure, rawShacl);
            boolean failed = !constraints.get("conforms").getAsBoolean();
            report.add("shacl", constraints);
            stage("data_constraints", failed ? "failed" : "passed", failed ? "Global fixture violates required SHACL constraints" : "Global fixture conforms to required SHACL constraints");
            for (JsonElement element : specs) {
                JsonObject spec = element.getAsJsonObject(), result = new JsonObject();
                String id = id(spec), kind = Manifest.text(spec, "kind");
                result.addProperty("id", id);
                Model data = spec.has("fixtures_ttl") ? infer(ModelFactory.createDefaultModel().add(ontology).add(parse(Manifest.text(spec, "fixtures_ttl")))) : closure;
                JsonElement expected, actual;
                boolean matches;
                if (kind.equals("shacl")) {
                    actual = ShaclStage.run(shapes, data, rawShacl);
                    JsonObject want = new JsonObject(); want.add("conforms", spec.get("expected_conforms"));
                    matches = actual.getAsJsonObject().get("conforms").equals(spec.get("expected_conforms"));
                    if (spec.has("expected_violations")) {
                        want.add("violations", spec.get("expected_violations"));
                        matches &= QueryStage.matches(spec.get("expected_violations"), actual.getAsJsonObject().get("violations"), false);
                    }
                    expected = want;
                } else {
                    expected = spec.get("expected"); actual = QueryStage.run(queries.get(id), data);
                    matches = QueryStage.matches(expected, actual, spec.has("comparison") && Manifest.text(spec, "comparison").equals("contains"));
                }
                result.add("expected", expected); result.add("actual", actual);
                result.addProperty("status", matches ? "passed" : "failed");
                result.addProperty("message", matches ? "Expected result matched" : "Actual result did not match the explicit oracle");
                cases.add(result); failed |= !matches;
            }
            stage("executable_expectations", failed ? "failed" : "passed", specs.size() + " required cases executed");
            stage("dl_consistency", "not_run", "Complete OWL DL reasoning is outside the admitted RDFS profile");
            report.addProperty("status", failed ? "failed" : "passed");
            exit = failed ? 2 : 0;
        } catch (UnsupportedOperationException error) {
            report.addProperty("status", "unsupported"); stage("admitted_profile", "unsupported", error.getMessage()); exit = 3;
        } catch (QueryCancelledException error) {
            report.addProperty("status", "timeout"); stage("execution", "timeout", "Query execution time limit exceeded"); exit = 4;
        } catch (IllegalArgumentException | RiotException error) {
            report.addProperty("status", "error"); stage("integrity_and_syntax", "error", error.getMessage()); exit = 3;
        } catch (Exception error) {
            report.addProperty("status", "error"); stage("engine", "error", error.getClass().getSimpleName() + ": " + error.getMessage()); exit = 4;
        }
        report.addProperty("finished_at", Instant.now().toString());
        try {
            Files.writeString(directory.resolve("report.json"), JSON.toJson(report));
            Files.writeString(directory.resolve("query-results.json"), JSON.toJson(cases));
            try (var stream = Files.newOutputStream(directory.resolve("shacl-report.ttl"))) { RDFDataMgr.write(stream, rawShacl, Lang.TURTLE); }
        } catch (Exception error) { System.err.println("Could not write runner report: " + error.getMessage()); return 4; }
        return exit;
    }

    static String libraryVersion() {
        // Shading replaces package manifests, so Jena.VERSION becomes <development>.
        // Read the dependency's retained Maven metadata instead of inventing a version.
        Properties metadata = new Properties();
        try (var stream = Runner.class.getResourceAsStream("/META-INF/maven/org.apache.jena/jena-core/pom.properties")) {
            if (stream == null) throw new IllegalStateException("Jena dependency metadata is missing");
            metadata.load(stream);
            return metadata.getProperty("version");
        } catch (java.io.IOException error) { throw new IllegalStateException("Cannot read Jena version", error); }
    }
    static String id(JsonObject spec) { return Manifest.text(spec, spec.has("test_id") ? "test_id" : "id"); }
    static Model parse(String text) {
        Model model = ModelFactory.createDefaultModel();
        RDFParser.fromString(text, Lang.TURTLE).checking(true).parse(model);
        if (model.size() > 50_000) throw new IllegalArgumentException("RDF triple limit exceeded");
        return model;
    }
    static Model infer(Model asserted) {
        InfModel inference = ModelFactory.createInfModel(ReasonerRegistry.getRDFSSimpleReasoner(), asserted);
        inference.prepare();
        Model closure = ModelFactory.createDefaultModel();
        var statements = inference.listStatements();
        while (statements.hasNext()) {
            if (closure.size() >= 100_000) throw new IllegalArgumentException("Inference closure triple limit exceeded");
            closure.add(statements.next());
        }
        return closure;
    }
    static String hash(Model model) throws Exception {
        List<String> lines = new ArrayList<>();
        model.getGraph().find().forEachRemaining(t -> lines.add(NodeFmtLib.strNT(t.getSubject()) + " " + NodeFmtLib.strNT(t.getPredicate()) + " " + NodeFmtLib.strNT(t.getObject()) + " .\n"));
        Collections.sort(lines);
        return Manifest.sha256(String.join("", lines).getBytes(StandardCharsets.UTF_8));
    }
    void stage(String name, String status, String message) {
        JsonObject stage = new JsonObject(); stage.addProperty("name", name); stage.addProperty("status", status); stage.addProperty("message", message); stages.add(stage);
    }
}
