package org.oe.studio;

import com.google.gson.*;
import org.apache.jena.rdf.model.*;
import org.apache.jena.shacl.*;
import java.util.*;

final class ShaclStage {
    static JsonObject run(Model shapes, Model data, Model reportOutput) {
        ValidationReport report = ShaclValidator.get().validate(Shapes.parse(shapes), data.getGraph());
        Model model = report.getModel();
        reportOutput.add(model);
        JsonObject result = new JsonObject(); result.addProperty("conforms", report.conforms());
        List<JsonObject> violations = new ArrayList<>();
        Property focus = model.createProperty(Profile.SH + "focusNode");
        model.listSubjectsWithProperty(focus).forEachRemaining(subject -> {
            JsonObject signature = new JsonObject();
            for (String key : List.of("focusNode", "path", "sourceShape", "severity")) {
                String predicate = switch (key) { case "path" -> "resultPath"; case "severity" -> "resultSeverity"; default -> key; };
                Statement statement = subject.getProperty(model.createProperty(Profile.SH + predicate));
                if (statement != null) {
                    RDFNode value = statement.getObject();
                    signature.addProperty(key, value.isURIResource() ? value.asResource().getURI() : value.toString());
                }
            }
            violations.add(signature);
        });
        violations.sort(Comparator.comparing(JsonElement::toString));
        JsonArray array = new JsonArray(); violations.forEach(array::add); result.add("violations", array);
        return result;
    }
}
