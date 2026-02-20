"""Tests de validation des extractions PDF."""

from pathlib import Path

from src.core.models import EleveExtraction, MatiereExtraction
from src.document.validation import check_classe_mismatch, validate_extraction
from src.document.yaml_template_parser import YamlTemplateParser

BULLETIN_TEST = (
    Path(__file__).resolve().parent.parent / "data" / "demo" / "Bulletin_TEST.pdf"
)


# =============================================================================
# validate_extraction
# =============================================================================


class TestValidateExtraction:
    def test_valid_bulletin(self):
        eleve = EleveExtraction(
            eleve_id="ELEVE_001",
            matieres=[
                MatiereExtraction(
                    nom="Maths", moyenne_eleve=14.5, appreciation="Bon travail"
                ),
                MatiereExtraction(
                    nom="Français", moyenne_eleve=12.0, appreciation="Peut mieux faire"
                ),
            ],
        )
        result = validate_extraction(eleve)
        assert result.is_valid
        assert result.errors == []
        assert result.warnings == []

    def test_no_matieres_is_blocking_error(self):
        eleve = EleveExtraction(eleve_id="ELEVE_001", matieres=[])
        result = validate_extraction(eleve)
        assert not result.is_valid
        assert len(result.errors) == 1
        assert "Aucune matière" in result.errors[0]

    def test_matieres_without_note_warns(self):
        eleve = EleveExtraction(
            eleve_id="ELEVE_001",
            matieres=[
                MatiereExtraction(nom="Maths", moyenne_eleve=14.5, appreciation="Bien"),
                MatiereExtraction(
                    nom="EPS", moyenne_eleve=None, appreciation="Sportif"
                ),
            ],
        )
        result = validate_extraction(eleve)
        assert result.is_valid
        assert any("sans note" in w for w in result.warnings)
        assert "EPS" in result.warnings[0]

    def test_matieres_without_appreciation_warns(self):
        eleve = EleveExtraction(
            eleve_id="ELEVE_001",
            matieres=[
                MatiereExtraction(nom="Maths", moyenne_eleve=14.5, appreciation="Bien"),
                MatiereExtraction(nom="Techno", moyenne_eleve=11.0, appreciation=""),
            ],
        )
        result = validate_extraction(eleve)
        assert result.is_valid
        assert any("sans appréciation" in w for w in result.warnings)
        assert "Techno" in result.warnings[0]

    def test_multiple_warnings(self):
        eleve = EleveExtraction(
            eleve_id="ELEVE_001",
            matieres=[
                MatiereExtraction(nom="Maths", moyenne_eleve=None, appreciation=""),
            ],
        )
        result = validate_extraction(eleve)
        assert result.is_valid
        assert len(result.warnings) == 2


# =============================================================================
# check_classe_mismatch
# =============================================================================


class TestCheckClasseMismatch:
    def test_match_same_level(self):
        assert check_classe_mismatch("5E", "5A_2024-2025") is None

    def test_mismatch_different_level(self):
        warning = check_classe_mismatch("5E", "3A_2024-2025")
        assert warning is not None
        assert "5E" in warning
        assert "3A_2024-2025" in warning

    def test_pdf_classe_none(self):
        assert check_classe_mismatch(None, "5A_2024-2025") is None

    def test_unparseable_classe(self):
        assert check_classe_mismatch("Terminale", "5A") is None


# =============================================================================
# Intégration : parsing + validation sur un vrai PDF
# =============================================================================


class TestBulletinTestPDF:
    def test_parse_and_validate(self):
        parser = YamlTemplateParser()
        eleve = parser.parse(BULLETIN_TEST, "ELEVE_TEST")
        result = validate_extraction(eleve)
        assert result.is_valid
        assert len(eleve.matieres) >= 10
        assert all(m.moyenne_eleve is not None for m in eleve.matieres)
        assert all(m.appreciation for m in eleve.matieres)

    def test_classe_extracted(self):
        parser = YamlTemplateParser()
        eleve = parser.parse(BULLETIN_TEST, "ELEVE_TEST")
        assert eleve.classe == "5A"
        assert eleve.trimestre == 1

    def test_no_classe_mismatch(self):
        parser = YamlTemplateParser()
        eleve = parser.parse(BULLETIN_TEST, "ELEVE_TEST")
        assert check_classe_mismatch(eleve.classe, "5A_2024-2025") is None

    def test_classe_mismatch_detected(self):
        parser = YamlTemplateParser()
        eleve = parser.parse(BULLETIN_TEST, "ELEVE_TEST")
        assert check_classe_mismatch(eleve.classe, "3B_2024-2025") is not None
