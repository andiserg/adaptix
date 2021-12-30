import inspect
from abc import abstractmethod, ABC
from dataclasses import dataclass, fields as dc_fields, is_dataclass, MISSING as DC_MISSING, Field as DCField
from enum import Enum
from inspect import Signature, Parameter
from operator import getitem
from types import MappingProxyType
from typing import Any, List, get_type_hints, Union, Generic, TypeVar, Callable, final, Type

from .definitions import NoDefault, DefaultValue, DefaultFactory, Default
from .essential import Mediator, CannotProvide, Request
from .request_cls import FieldRM, TypeHintRM
from .static_provider import StaticProvider, static_provision_action
from ..type_tools import is_typed_dict_class, is_named_tuple_class

T = TypeVar('T')


class GetterKind(Enum):
    ATTR = 0
    ITEM = 1

    def to_function(self) -> Callable[[Any, str], Any]:
        return _GETTER_KIND_TO_FUNCTION[self]  # type: ignore


_GETTER_KIND_TO_FUNCTION = {
    GetterKind.ATTR: getattr,
    GetterKind.ITEM: getitem,
}


class ExtraSkip:
    def __new__(cls, *args, **kwargs):
        raise RuntimeError(f"Cannot create instance of {cls}")


class ExtraForbid:
    def __new__(cls, *args, **kwargs):
        raise RuntimeError(f"Cannot create instance of {cls}")


class ExtraKwargs:
    def __new__(cls, *args, **kwargs):
        raise RuntimeError(f"Cannot create instance of {cls}")


@dataclass(frozen=True)
class ExtraTargets:
    fields: List[str]


Extra = Union[Type[ExtraSkip], Type[ExtraForbid], Type[ExtraKwargs], ExtraTargets]

# Factory should replace None with ExtraSkip or ExtraForbid
UnboundExtra = Union[None, Type[ExtraKwargs], ExtraTargets]

DefaultExtra = Union[Type[ExtraSkip], Type[ExtraForbid]]


class CfgDefaultExtra(Request[DefaultExtra]):
    pass


@dataclass
class InputFieldsFigure:
    fields: List[FieldRM]
    extra: UnboundExtra


@dataclass
class OutputFieldsFigure:
    fields: List[FieldRM]
    getter_kind: GetterKind


class BaseFFRequest(TypeHintRM[T], Generic[T]):
    pass


class InputFFRequest(BaseFFRequest[InputFieldsFigure]):
    pass


class OutputFFRequest(BaseFFRequest[OutputFieldsFigure]):
    pass


def get_func_iff(func, params_slice=slice(0, None)) -> InputFieldsFigure:
    params = list(
        inspect.signature(func).parameters.values()
    )[params_slice]

    if not all(
        p.kind in (
            Parameter.POSITIONAL_OR_KEYWORD,
            Parameter.KEYWORD_ONLY,
            Parameter.VAR_KEYWORD
        )
        for p in params
    ):
        raise ValueError(
            'Can not create consistent InputFieldsFigure'
            ' from the function that has not only'
            ' POSITIONAL_OR_KEYWORD or KEYWORD_ONLY or VAR_KEYWORD'
            ' parameters'
        )

    extra: UnboundExtra
    if any(p.kind == Parameter.VAR_KEYWORD for p in params):
        extra = ExtraKwargs
    else:
        extra = None

    return InputFieldsFigure(
        fields=[
            FieldRM(
                type=(
                    Any
                    if param.annotation is Signature.empty
                    else param.annotation
                ),
                field_name=param.name,
                default=(
                    NoDefault(field_is_required=True)
                    if param.default is Signature.empty
                    else DefaultValue(param.default)
                ),
                metadata=MappingProxyType({}),
            )
            for param in params
            if param.kind != Parameter.VAR_KEYWORD
        ],
        extra=extra,
    )


class TypeOnlyInputFFProvider(StaticProvider, ABC):
    # noinspection PyUnusedLocal
    @final
    @static_provision_action(InputFFRequest)
    def _provide_input_fields_figure(self, mediator: Mediator, request: InputFFRequest) -> InputFieldsFigure:
        return self._get_input_fields_figure(request.type)

    @abstractmethod
    def _get_input_fields_figure(self, tp) -> InputFieldsFigure:
        pass


class TypeOnlyOutputFFProvider(StaticProvider, ABC):
    # noinspection PyUnusedLocal
    @final
    @static_provision_action(OutputFFRequest)
    def _provide_output_fields_figure(self, mediator: Mediator, request: OutputFFRequest) -> OutputFieldsFigure:
        return self._get_output_fields_figure(request.type)

    @abstractmethod
    def _get_output_fields_figure(self, tp) -> OutputFieldsFigure:
        pass


class NamedTupleFieldsProvider(TypeOnlyInputFFProvider, TypeOnlyOutputFFProvider):
    def _get_input_fields_figure(self, tp) -> InputFieldsFigure:
        if not is_named_tuple_class(tp):
            raise CannotProvide

        return get_func_iff(tp.__new__, slice(1, None))

    def _get_output_fields_figure(self, tp) -> OutputFieldsFigure:
        return OutputFieldsFigure(
            fields=self._get_input_fields_figure(tp).fields,
            getter_kind=GetterKind.ATTR,
        )


class TypedDictFieldsProvider(TypeOnlyInputFFProvider, TypeOnlyOutputFFProvider):
    def _get_fields(self, tp):
        if not is_typed_dict_class(tp):
            raise CannotProvide

        is_required = tp.__total__

        return [
            FieldRM(
                type=tp,
                field_name=name,
                default=NoDefault(field_is_required=is_required),
                metadata=MappingProxyType({}),
            )
            for name, tp in get_type_hints(tp).items()
        ]

    def _get_input_fields_figure(self, tp):
        return InputFieldsFigure(
            fields=self._get_fields(tp),  # noqa
            extra=None,
        )

    def _get_output_fields_figure(self, tp):
        return OutputFieldsFigure(
            fields=self._get_fields(tp),  # noqa
            getter_kind=GetterKind.ITEM,
        )


def get_dc_default(field: DCField) -> Default:
    if field.default is not DC_MISSING:
        return DefaultValue(field.default)
    if field.default_factory is not DC_MISSING:
        return DefaultFactory(field.default_factory)
    return NoDefault(field_is_required=True)


class DataclassFieldsProvider(TypeOnlyInputFFProvider, TypeOnlyOutputFFProvider):
    """This provider does not work properly if __init__ signature differs from
    that would be created by dataclass decorator.

    It happens because we can not distinguish __init__ that generated
    by @dataclass and __init__ that created by other ways.
    And we can not analyze only __init__ signature
    because @dataclass uses private constant
    as default value for fields with default_factory
    """

    def _get_fields_filtered(self, tp, filer_func):
        if not is_dataclass(tp):
            raise CannotProvide

        return [
            FieldRM(
                type=fld.type,
                field_name=fld.name,
                default=get_dc_default(fld),
                metadata=fld.metadata,
            )
            for fld in dc_fields(tp)
            if filer_func(fld)
        ]

    def _get_input_fields_figure(self, tp):
        return InputFieldsFigure(
            fields=self._get_fields_filtered(
                tp, lambda fld: fld.init
            ),
            extra=None,
        )

    def _get_output_fields_figure(self, tp):
        return OutputFieldsFigure(
            fields=self._get_fields_filtered(
                tp, lambda fld: True
            ),
            getter_kind=GetterKind.ATTR
        )


class ClassInitFieldsProvider(TypeOnlyInputFFProvider):
    def _get_input_fields_figure(self, tp):
        if not isinstance(tp, type):
            raise CannotProvide

        try:
            return get_func_iff(
                tp.__init__, slice(1, None)
            )
        except ValueError:
            raise CannotProvide
