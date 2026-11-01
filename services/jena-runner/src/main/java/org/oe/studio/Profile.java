package org.oe.studio;

import com.google.gson.*;
import org.apache.jena.rdf.model.*;
import org.apache.jena.vocabulary.*;
import java.util.*;

final class Profile {
    static final String SH = "http://www.w3.org/ns/shacl#";
    static final Set<String> SHACL = Set.of("targetClass", "targetNode", "targetSubjectsOf", "targetObjectsOf", "property", "path", "minCount", "maxCount", "datatype", "class", "nodeKind", "minLength", "maxLength", "minInclusive", "maxInclusive", "minExclusive", "maxExclusive", "pattern", "flags", "name", "description", "message", "severity", "node", "closed", "ignoredProperties", "in", "hasValue", "and", "or", "not", "xone", "qualifiedValueShape", "qualifiedMinCount", "qualifiedMaxCount", "qualifiedValueShapesDisjoint", "equals", "disjoint", "lessThan", "lessThanOrEquals", "uniqueLang", "languageIn");
    final Set<String> predicates = new HashSet<>(), types = new HashSet<>(), declaredProperties = new HashSet<>();
    final JsonArray limitations;

    Profile(JsonObject settings, Model ontology) {
        if (!Manifest.text(settings, "id").equals("rdfs")) throw new UnsupportedOperationException("Unsupported profile");
        settings.getAsJsonArray("allowed_predicates").forEach(v -> predicates.add(v.getAsString()));
        settings.getAsJsonArray("allowed_declaration_types").forEach(v -> types.add(v.getAsString()));
        limitations = settings.getAsJsonArray("limitations");
        ontology.listStatements(null, RDF.type, (RDFNode)null).forEachRemaining(s -> {
            if (Set.of(RDF.Property, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty).contains(s.getObject()))
                declaredProperties.add(s.getSubject().getURI());
        });
    }

    static boolean reserved(String iri) {
        return iri.startsWith(OWL.NS) || iri.startsWith(RDF.uri) || iri.startsWith(RDFS.uri) || iri.startsWith(SH);
    }

    void check(Model model, boolean fixture) {
        model.listStatements().forEachRemaining(s -> {
            if (!s.getSubject().isURIResource() || s.getObject().isAnon())
                throw new UnsupportedOperationException("Ontology/data blank nodes and RDF lists are unsupported");
            String predicate = s.getPredicate().getURI();
            if (!predicates.contains(predicate) && !( !reserved(predicate) && (fixture || declaredProperties.contains(predicate))))
                throw new UnsupportedOperationException("Unsupported predicate: " + predicate);
            if (s.getPredicate().equals(RDF.type) && (!s.getObject().isURIResource() ||
                (reserved(s.getResource().getURI()) && !types.contains(s.getResource().getURI()))))
                throw new UnsupportedOperationException("Unsupported declaration type: " + s.getObject());
            if (Set.of(RDFS.subClassOf, RDFS.subPropertyOf, RDFS.domain, RDFS.range).contains(s.getPredicate()) && !s.getObject().isURIResource())
                throw new UnsupportedOperationException("Schema relationship objects must be IRIs");
        });
    }

    static void checkShapes(Model model) {
        model.listStatements().forEachRemaining(s -> {
            String predicate = s.getPredicate().getURI();
            if (s.getPredicate().equals(RDF.type)) {
                if (!s.getObject().isURIResource() || !Set.of(SH + "NodeShape", SH + "PropertyShape").contains(s.getResource().getURI()))
                    throw new UnsupportedOperationException("Unsupported SHACL type: " + s.getObject());
            } else if (!(predicate.startsWith(SH) && SHACL.contains(predicate.substring(SH.length()))) &&
                       !Set.of(RDF.first, RDF.rest, RDFS.label, RDFS.comment).contains(s.getPredicate()))
                throw new UnsupportedOperationException("Unsupported SHACL predicate: " + predicate);
            if (predicate.equals(SH + "path") && !s.getObject().isURIResource())
                throw new UnsupportedOperationException("Only simple IRI SHACL paths are supported");
        });
    }
}
