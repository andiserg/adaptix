from types import MappingProxyType
from typing import Any

import pytest

from dataclass_factory_30.feature_requirement import has_pos_only_params
from dataclass_factory_30.provider import DefaultValue, NoDefault, CannotProvide, ClassInitInputFigureProvider, \
    InputFigure, ExtraKwargs
from dataclass_factory_30.provider.request_cls import ParamKind, InputFieldRM


class Valid1:
    def __init__(self, a, b: int, c: str = 'abc', *, d):
        self.a = a
        self.b = b
        self.c = c
        self.d = d


class Valid2Kwargs:
    def __init__(self, a, b: int, c: str = 'abc', *, d, **data):
        self.a = a
        self.b = b
        self.c = c
        self.d = d
        self.data = data


VALID_FIELDS = (
    InputFieldRM(
        type=Any,
        name='a',
        default=NoDefault(),
        is_required=True,
        metadata=MappingProxyType({}),
        param_kind=ParamKind.POS_OR_KW,
    ),
    InputFieldRM(
        type=int,
        name='b',
        default=NoDefault(),
        is_required=True,
        metadata=MappingProxyType({}),
        param_kind=ParamKind.POS_OR_KW,
    ),
    InputFieldRM(
        type=str,
        name='c',
        default=DefaultValue('abc'),
        is_required=False,
        metadata=MappingProxyType({}),
        param_kind=ParamKind.POS_OR_KW,
    ),
    InputFieldRM(
        type=Any,
        name='d',
        default=NoDefault(),
        is_required=True,
        metadata=MappingProxyType({}),
        param_kind=ParamKind.KW_ONLY,
    ),
)


def test_extra_none():
    assert (
        ClassInitInputFigureProvider()._get_input_figure(Valid1)
        ==
        InputFigure(
            constructor=Valid1,
            extra=None,
            fields=VALID_FIELDS,
        )
    )


def test_extra_kwargs():
    assert (
        ClassInitInputFigureProvider()._get_input_figure(Valid2Kwargs)
        ==
        InputFigure(
            constructor=Valid2Kwargs,
            extra=ExtraKwargs(),
            fields=VALID_FIELDS,
        )
    )


@has_pos_only_params
def test_pos_only():
    class HasPosOnly:
        def __init__(self, a, /, b):
            self.a = a
            self.b = b

    assert (
        ClassInitInputFigureProvider()._get_input_figure(HasPosOnly)
        ==
        InputFigure(
            constructor=HasPosOnly,
            extra=None,
            fields=(
                InputFieldRM(
                    type=Any,
                    name='a',
                    default=NoDefault(),
                    is_required=True,
                    metadata=MappingProxyType({}),
                    param_kind=ParamKind.POS_ONLY,
                ),
                InputFieldRM(
                    type=Any,
                    name='b',
                    default=NoDefault(),
                    is_required=True,
                    metadata=MappingProxyType({}),
                    param_kind=ParamKind.POS_OR_KW,
                ),
            ),
        )
    )


def test_var_arg():
    class HasVarArg:
        def __init__(self, a, b, *args):
            self.a = a
            self.b = b
            self.args = args

    with pytest.raises(CannotProvide):
        ClassInitInputFigureProvider()._get_input_figure(
            HasVarArg
        )