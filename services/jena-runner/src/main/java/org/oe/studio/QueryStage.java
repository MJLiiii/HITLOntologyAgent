package org.oe.studio;

import com.google.gson.*;
import org.apache.jena.query.*;
import org.apache.jena.rdf.model.*;
import org.apache.jena.sparql.algebra.*;
import org.apache.jena.sparql.algebra.op.*;
import org.apache.jena.sparql.expr.*;
import java.util.*;
import java.util.concurrent.TimeUnit;

final class QueryStage {
    static final Set<Class<?>> ALLOWED_OPS = Set.of(OpBGP.class, OpTriple.class, OpJoin.class, OpSequence.class, OpUnion.class, OpLeftJoin.class, OpFilter.class, OpProject.class, OpDistinct.class, OpReduced.class, OpSlice.class, OpTable.class, OpNull.class);
    static final Set<Class<?>> ALLOWED_FUNCTIONS = Set.of(E_Equals.class, E_NotEquals.class, E_LessThan.class, E_GreaterThan.class, E_LessThanOrEqual.class, E_GreaterThanOrEqual.class, E_Bound.class, E_LogicalNot.class, E_LogicalAnd.class, E_LogicalOr.class);

    static Query parse(JsonObject spec) {
        Query query;
        try { query = QueryFactory.create(Manifest.text(spec, "query"), Syntax.syntaxSPARQL_11); }
        catch (RuntimeException error) { throw new UnsupportedOperationException("Only parsed SPARQL 1.1 ASK/SELECT queries are accepted", error); }
        String kind = Manifest.text(spec, "kind");
        if (!(kind.equals("ask") && query.isAskType() || kind.equals("select_rows") && query.isSelectType()))
            throw new UnsupportedOperationException("Query type must match ask or select_rows case kind");
        if (query.hasDatasetDescription()) throw new UnsupportedOperationException("FROM and remote datasets are prohibited");
        check(Algebra.compile(query));
        if (!spec.has("expected")) throw new IllegalArgumentException("Query case requires an explicit expected result");
        if (kind.equals("ask") && !(spec.get("expected").isJsonPrimitive() && spec.getAsJsonPrimitive("expected").isBoolean()))
            throw new IllegalArgumentException("ASK expected value must be boolean");
        if (kind.equals("select_rows") && !spec.get("expected").isJsonArray())
            throw new IllegalArgumentException("SELECT expected value must be typed binding rows");
        if (spec.has("comparison") && !Set.of("exact", "contains").contains(Manifest.text(spec, "comparison")))
            throw new IllegalArgumentException("Unsupported SELECT comparison mode");
        return query;
    }

    private static void expression(Expr expr) {
        if (expr.isVariable() || expr.isConstant()) return;
        if (!expr.isFunction() || !ALLOWED_FUNCTIONS.contains(expr.getClass()))
            throw new UnsupportedOperationException("Query expression/function is not admitted: " + expr.getClass().getSimpleName());
        expr.getFunction().getArgs().forEach(QueryStage::expression);
    }

    private static void check(Op op) {
        if (!ALLOWED_OPS.contains(op.getClass())) throw new UnsupportedOperationException("Query algebra operation is not admitted: " + op.getName());
        if (op instanceof OpFilter filter) filter.getExprs().forEach(QueryStage::expression);
        if (op instanceof OpLeftJoin join && join.getExprs() != null) join.getExprs().forEach(QueryStage::expression);
        if (op instanceof Op1 one) check(one.getSubOp());
        else if (op instanceof Op2 two) { check(two.getLeft()); check(two.getRight()); }
        else if (op instanceof OpN many) many.getElements().forEach(QueryStage::check);
    }

    static JsonElement run(Query query, Model model) {
        try (QueryExecution execution = QueryExecution.model(model).query(query).timeout(10, TimeUnit.SECONDS).build()) {
            execution.getContext().set(ARQ.enablePropertyFunctions, false);
            if (query.isAskType()) return new JsonPrimitive(execution.execAsk());
            ResultSet results = execution.execSelect();
            List<String> variables = new ArrayList<>(results.getResultVars());
            Collections.sort(variables);
            List<JsonObject> rows = new ArrayList<>();
            while (results.hasNext()) {
                if (rows.size() >= 10_000) throw new IllegalArgumentException("SELECT result row limit exceeded; results are not silently truncated");
                QuerySolution row = results.next();
                JsonObject object = new JsonObject();
                for (String variable : variables) if (row.contains(variable)) object.add(variable, term(row.get(variable)));
                rows.add(object);
            }
            rows.sort(Comparator.comparing(JsonElement::toString));
            JsonArray array = new JsonArray(); rows.forEach(array::add); return array;
        }
    }

    static JsonObject term(RDFNode value) {
        JsonObject term = new JsonObject();
        if (value.isURIResource()) { term.addProperty("kind", "iri"); term.addProperty("value", value.asResource().getURI()); }
        else if (value.isLiteral()) {
            Literal literal = value.asLiteral();
            term.addProperty("kind", "literal"); term.addProperty("value", literal.getLexicalForm());
            if (literal.getDatatypeURI() != null) term.addProperty("datatype", literal.getDatatypeURI());
            if (!literal.getLanguage().isEmpty()) term.addProperty("lang", literal.getLanguage());
        } else throw new UnsupportedOperationException("Blank node query results cannot be compared canonically");
        return term;
    }

    static boolean matches(JsonElement expected, JsonElement actual, boolean contains) {
        if (!expected.isJsonArray() || !actual.isJsonArray()) return expected.equals(actual);
        List<JsonElement> remaining = new ArrayList<>(); actual.getAsJsonArray().forEach(remaining::add);
        for (JsonElement row : expected.getAsJsonArray()) if (!remaining.remove(row)) return false;
        return contains || remaining.isEmpty();
    }
}
