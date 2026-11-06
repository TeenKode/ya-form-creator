"""Synthetic non-GUI regressions from the 1.6.2 review."""
import unittest
import engine
from check_agent_form import validate_schema
class ChoiceConstraints(unittest.TestCase):
    def test_required_choice_cannot_forbid_every_answer(self):
        config={"form":{"name":"Synthetic"},"questions":[{"type":"checkbox","slug":"q1","label":"Synthetic","options":["A","B"],"required":True,"max_choices":0}]}
        with self.assertRaises(engine.ConfigError): engine.validate_config(config)
        with self.assertRaises(engine.ConfigError): validate_schema(config)
        config["questions"][0]["required"]=False
        engine.validate_config(config)
        validate_schema(config)
