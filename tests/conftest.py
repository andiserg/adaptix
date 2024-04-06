import pytest
from tests_helpers import ByTrailSelector, ModelSpecSchema, cond_list, parametrize_model_spec

from adaptix import DebugTrail
from adaptix._internal.feature_requirement import HAS_ATTRS_PKG, HAS_PY_312, HAS_PYDANTIC_PKG


@pytest.fixture(params=[False, True], ids=lambda x: f"strict_coercion={x}")
def strict_coercion(request):
    return request.param


@pytest.fixture(params=[DebugTrail.DISABLE, DebugTrail.FIRST, DebugTrail.ALL])
def debug_trail(request):
    return request.param


@pytest.fixture()
def trail_select(debug_trail):
    return ByTrailSelector(debug_trail)


@pytest.fixture()
def model_spec() -> ModelSpecSchema:  # noqa: PT004
    ...


@pytest.fixture()
def src_model_spec() -> ModelSpecSchema:  # noqa: PT004
    ...


@pytest.fixture()
def dst_model_spec() -> ModelSpecSchema:  # noqa: PT004
    ...


def pytest_generate_tests(metafunc):
    parametrize_model_spec("model_spec", metafunc)
    parametrize_model_spec("src_model_spec", metafunc)
    parametrize_model_spec("dst_model_spec", metafunc)


collect_ignore_glob = [
    *cond_list(not HAS_PY_312, ["*_312.py"]),
    *cond_list(not HAS_ATTRS_PKG, ["*_attrs.py", "*_attrs_*.py"]),
    *cond_list(not HAS_PYDANTIC_PKG, ["*_pydantic.py", "*_pydantic_*.py"]),
]
