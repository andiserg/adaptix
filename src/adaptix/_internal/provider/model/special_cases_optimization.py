from typing import Optional, TypeVar, Union

from adaptix._internal.load_error import TypeLoadError
from adaptix._internal.model_tools import DefaultFactory, DefaultValue
from adaptix._internal.provider.model.crown_definitions import Sieve

as_is_stub = lambda x: x  # noqa: E731  # pylint: disable=unnecessary-lambda-assignment


S = TypeVar('S', bound=Sieve)


_DEFAULT_CLAUSE_ATTR_NAME = '_adaptix_default_clause'


def with_default_clause(sieve: S, default: Union[DefaultValue, DefaultFactory]) -> S:
    setattr(sieve, _DEFAULT_CLAUSE_ATTR_NAME, default)
    return sieve


def get_default_clause(sieve: Sieve) -> Optional[Union[DefaultValue, DefaultFactory]]:
    return getattr(sieve, _DEFAULT_CLAUSE_ATTR_NAME, None)


def none_loader(data):
    if data is None:
        return None
    raise TypeLoadError(None)