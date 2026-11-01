package org.oe.studio;

import com.google.gson.*;
import org.apache.jena.rdf.model.*;
import org.apache.jena.shacl.*;
import java.util.*;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

final class ShaclStage {
    static JsonObject run(Model shapes, Model data, Model reportOutput) {
        ValidationReport report = ShaclValidator.get().validate(Shapes.parse(shapes), data.getGraph());
        Model model = report.getModel();
        reportOutput.add(model);
        JsonObject result = new JsonObject(); result.addProperty("conforms", report.conforms());
        result.addProperty("signature_format", "named-or-leaf-shape-sha256-v1");
        List<JsonObject> violations = new ArrayList<>();
        Property focus = model.createProperty(Profile.SH + "focusNode");
        model.listSubjectsWithProperty(focus).forEachRemaining(subject -> {
            JsonObject signature = new JsonObject();
            for (String key : List.of("focusNode", "path", "sourceShape", "severity")) {
                String predicate = switch (key) { case "path" -> "resultPath"; case "severity" -> "resultSeverity"; default -> key; };
                Statement statement = subject.getProperty(model.createProperty(Profile.SH + predicate));
                if (statement != null) {
                    RDFNode value = statement.getObject();
                    signature.addProperty(key, key.equals("sourceShape") ? sourceShape(shapes, value) :
                        (value.isURIResource() ? value.asResource().getURI() : value.toString()));
                }
            }
            violations.add(signature);
        });
        violations.sort(Comparator.comparing(JsonElement::toString));
        JsonArray array = new JsonArray(); violations.forEach(array::add); result.add("violations", array);
        return result;
    }

    /** Stable leaf identity; complex anonymous shapes retain their raw identity.
     * Five length-prefixed UTF-8 fields preserve datatype/language/lexical values.
     */
    static String sourceShape(Model shapes, RDFNode shape) {
        if (shape.isURIResource()) return shape.asResource().getURI();
        if (!shape.isAnon()) return shape.toString();
        List<String> rows = new ArrayList<>();
        for (Statement statement : shapes.listStatements(shape.asResource(), null, (RDFNode)null).toList()) {
            RDFNode object = statement.getObject();
            if (object.isAnon()) return shape.toString();
            List<String> fields = new ArrayList<>();
            fields.add(statement.getPredicate().getURI());
            if (object.isURIResource()) fields.addAll(List.of("iri", object.asResource().getURI(), "", ""));
            else {
                Literal literal = object.asLiteral();
                fields.addAll(List.of("literal", literal.getLexicalForm(),
                    literal.getDatatypeURI() == null ? "" : literal.getDatatypeURI(), literal.getLanguage()));
            }
            ByteArrayOutputStream encoded = new ByteArrayOutputStream();
            for (String field : fields) {
                byte[] bytes = field.getBytes(StandardCharsets.UTF_8);
                encoded.writeBytes((bytes.length + ":").getBytes(StandardCharsets.UTF_8));
                encoded.writeBytes(bytes);
            }
            rows.add(HexFormat.of().formatHex(encoded.toByteArray()));
        }
        if (rows.isEmpty()) return shape.toString();
        Collections.sort(rows);
        try {
            byte[] content = (String.join("\n", rows) + "\n").getBytes(StandardCharsets.UTF_8);
            return "urn:oe:shacl-leaf:sha256:" + HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content));
        } catch (NoSuchAlgorithmException impossible) { throw new AssertionError(impossible); }
    }
}
