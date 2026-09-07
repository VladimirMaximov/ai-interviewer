import unittest

from product_engineering import schemas


SCHEMAS = [
    schemas.PRODUCT_RESEARCH_SCHEMA,
    schemas.PRODUCT_DESCRIPTION_SCHEMA,
    schemas.SEGMENTS_SCHEMA,
    schemas.ICP_SCHEMA,
    schemas.INTERVIEW_SCHEMA,
    schemas.PAIN_MAP_SCHEMA,
    schemas.JTBD_SCHEMA,
    schemas.VPC_SCHEMA,
    schemas.HYPOTHESES_SCHEMA,
    schemas.LEAN_CANVAS_SCHEMA,
]


def assert_strict_objects(test: unittest.TestCase, schema):
    if schema.get("type") == "object":
        test.assertFalse(schema.get("additionalProperties", True))
        test.assertEqual(set(schema["required"]), set(schema["properties"]))
        for child in schema["properties"].values():
            assert_strict_objects(test, child)
    if schema.get("type") == "array":
        assert_strict_objects(test, schema["items"])


class SchemaTests(unittest.TestCase):
    def test_all_object_schemas_are_strict(self) -> None:
        for schema in SCHEMAS:
            with self.subTest(schema=schema):
                assert_strict_objects(self, schema)

    def test_limit_does_not_mutate_source(self) -> None:
        limited = schemas.limited_schema(
            schemas.PRODUCT_RESEARCH_SCHEMA, ("products",), 2
        )
        self.assertEqual(limited["properties"]["products"]["maxItems"], 2)
        self.assertNotIn("maxItems", schemas.PRODUCT_RESEARCH_SCHEMA["properties"]["products"])


if __name__ == "__main__":
    unittest.main()
