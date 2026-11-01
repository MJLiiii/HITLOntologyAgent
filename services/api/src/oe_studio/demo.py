NS = "https://example.org/oe-demo/"
PREFIX = """@prefix demo: <https://example.org/oe-demo/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
"""
ONTOLOGY = PREFIX + """
demo:Service a owl:Class ; rdfs:label "Service" .
demo:CriticalService a owl:Class ; rdfs:subClassOf demo:Service ; rdfs:label "Critical service" .
demo:Team a owl:Class ; rdfs:label "Team" .
demo:hasOwner a owl:ObjectProperty ; rdfs:domain demo:Service ; rdfs:range demo:Team ; rdfs:label "has owner" .
demo:PayrollService a demo:CriticalService ; demo:hasOwner demo:OperationsTeam ; rdfs:label "Payroll Service" .
demo:AnalyticsService a demo:Service ; demo:hasOwner demo:DataTeam ; rdfs:label "Analytics Service" .
demo:OperationsTeam a demo:Team ; rdfs:label "Operations Team" .
demo:DataTeam a demo:Team ; rdfs:label "Data Team" .
"""
FIXTURES = PREFIX + """
demo:PayrollService a demo:CriticalService ; demo:hasOwner demo:OperationsTeam .
demo:AnalyticsService a demo:Service ; demo:hasOwner demo:DataTeam .
"""
SHAPES = """@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix demo: <https://example.org/oe-demo/> .
demo:ServiceShape a sh:NodeShape ; sh:targetClass demo:Service ;
 sh:property [ sh:path demo:hasOwner ; sh:minCount 1 ; sh:nodeKind sh:IRI ] .
"""
QUESTIONS = [
    {"id": "CQ-01", "question": "Is Payroll Service a service through the critical-service hierarchy?", "required": True,
     "sparql_query": "PREFIX demo: <https://example.org/oe-demo/> ASK { demo:PayrollService a demo:Service }"},
    {"id": "CQ-02", "question": "Does Payroll Service have Operations Team as owner?", "required": True,
     "sparql_query": "PREFIX demo: <https://example.org/oe-demo/> ASK { demo:PayrollService demo:hasOwner demo:OperationsTeam }"},
]
TESTS = [{"test_id": q["id"], "kind": "ask", "query": q["sparql_query"], "expected": True,
          "name": q["question"]} for q in QUESTIONS]
SOURCES = [
    ("Service ownership policy", "Every service has an accountable owner. Payroll Service is owned by Operations Team. Analytics Service is owned by Data Team. Ownership identifies the team responsible for maintaining the service."),
    ("Service classification guide", "A critical service is a kind of service. Payroll Service is classified as a critical service. Analytics Service is a service. These are synthetic examples for demonstrating ontology engineering."),
    ("Modelling conventions", "Services and teams are separate concepts. The hasOwner relationship connects a service to a team. A required owner is a data constraint; domain and range infer types and do not enforce required fields."),
]
POLICY = {"id": "demo-human-approval-v1", "profile": "rdfs", "required_assessment": True,
          "maximum_repairs": 2, "human_approval": True, "demo_only": True}
