from dataclasses import replace

import pytest

from ms_toolbox.catalog import load_catalog


def test_catalog_has_a_pinned_recipe_without_path_discovery(tmp_path):
    app = load_catalog()["amdockvs"]
    recipe = app.recipe(tmp_path)
    assert recipe.pip == (f"AMDockVS=={app.version}",)
    assert recipe.commands == ()
    assert recipe.prefix == str(tmp_path / "apps/amdockvs")
    assert "python=3.12" in recipe.conda
    assert app.manifest().app_id == "amdockvs"


@pytest.mark.parametrize("field,value", [
    ("app_id", "../app"), ("distribution", "--extra-index-url=evil"),
    ("distribution", "app @ https://evil.test/app.whl"), ("version", "latest"),
    ("package", "app;print(1)"), ("configurations", ("app:factory()",)),
    ("color", "blue"), ("repository", "javascript:alert(1)"),
])
def test_catalog_rejects_unsafe_or_incomplete_entries(field, value):
    with pytest.raises(ValueError):
        replace(load_catalog()["amdockvs"], **{field: value})
