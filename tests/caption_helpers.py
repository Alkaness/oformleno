"""Mutations of generated captions for saved/reopened DOCX rule tests."""

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from oformleno.model import DocumentModel
from oformleno.ruleset import load_ruleset


def example(eom_fixtures, rule_id, case="good"):
    document = Document(eom_fixtures[case])
    rule = next(rule for rule in load_ruleset().rules if rule.id == rule_id)
    paragraph = next(p for p in document.paragraphs if p.style.name == rule.params["style"])
    return document, paragraph, rule


def code_nodes(paragraph):
    return list(paragraph._p.iter(qn("w:instrText")))


def change_code(paragraph, old, new):
    node = next(node for node in code_nodes(paragraph) if old in node.text)
    node.text = node.text.replace(old, new)


def child(parent, tag, **attributes):
    node = OxmlElement("w:" + tag)
    for name, value in attributes.items():
        node.set(qn("w:" + name), str(value))
    parent.append(node)
    return node


def visible_runs(document, paragraph):
    return [run for run in DocumentModel(document).runs(paragraph) if run.text]
