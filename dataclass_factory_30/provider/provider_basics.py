from abc import ABC, abstractmethod
from dataclasses import dataclass
from inspect import isabstract
from typing import TypeVar, Union, Type, Tuple, Callable, Any, Generic

from .class_dispatcher import ClassDispatcherKeysView
from .definitions import ParseError, PARSER_COMPAT_EXCEPTIONS
from .essential import Provider, Mediator, CannotProvide, Request, RequestDispatcher
from .request_cls import TypeHintRM, FieldNameRM
from .static_provider import StaticProvider, static_provision_action
from ..common import TypeHint, Parser
from ..type_tools import is_protocol, normalize_type, is_subclass_soft
from ..type_tools.normalize_type import FORBID_ZERO_ARGS

T = TypeVar('T')


class RequestChecker(ABC):
    @abstractmethod
    def get_allowed_request_classes(self) -> Tuple[Type[Request], ...]:
        raise NotImplementedError

    @abstractmethod
    def _check_request(self, request) -> None:
        """Raise CannotProvide if the request does not meet the conditions"""
        raise NotImplementedError

    def __call__(self, request: Request) -> None:
        """Raise CannotProvide if the request does not meet the conditions"""
        allowed = self.get_allowed_request_classes()
        if isinstance(request, allowed):
            self._check_request(request)
        raise CannotProvide(f'Only instances of {allowed} are allowed')


@dataclass
class FieldNameRC(RequestChecker):
    field_name: str

    def get_allowed_request_classes(self) -> Tuple[Type[Request], ...]:
        return (FieldNameRM,)

    def _check_request(self, request: FieldNameRM) -> None:
        if self.field_name == request.field_name:
            return
        raise CannotProvide(f'field_name must be a {self.field_name!r}')


class ExactTypeRC(RequestChecker):
    def __init__(self, tp: TypeHint):
        self.norm = normalize_type(tp)

    def get_allowed_request_classes(self) -> Tuple[Type[Request], ...]:
        return (TypeHintRM,)

    def _check_request(self, request: TypeHintRM) -> None:
        if normalize_type(request.type) == self.norm:
            return
        raise CannotProvide(f'{request.type} must be a equal to {self.norm.source}')


@dataclass
class SubclassRC(RequestChecker):
    type_: type

    def get_allowed_request_classes(self) -> Tuple[Type[Request], ...]:
        return (TypeHintRM,)

    def _check_request(self, request: TypeHintRM) -> None:
        if is_subclass_soft(request.type, self.type_):
            return
        raise CannotProvide(f'{request.type} must be a subclass of {self.type_}')


class ExactOriginRC(RequestChecker):
    def __init__(self, origin):
        self.origin = origin

    def get_allowed_request_classes(self) -> Tuple[Type[Request], ...]:
        return (TypeHintRM,)

    def _check_request(self, request: TypeHintRM) -> None:
        if normalize_type(request.type).origin == self.origin:
            return
        raise CannotProvide(f'{request.type} must have origin {self.origin}')


def create_type_hint_req_checker(tp: TypeHint) -> RequestChecker:
    if isinstance(tp, type) and (is_protocol(tp) or isabstract(tp)):
        return SubclassRC(tp)

    if tp in FORBID_ZERO_ARGS:
        return ExactOriginRC(tp)

    try:
        return ExactTypeRC(tp)
    except ValueError:
        raise ValueError(f'Can not create RequestChecker from {tp}')


def create_req_checker(pred: Union[TypeHint, str]) -> RequestChecker:
    if isinstance(pred, str):
        return FieldNameRC(pred)

    return create_type_hint_req_checker(pred)


class NextProvider(StaticProvider):
    @static_provision_action(Request)
    def _np_proxy_provide(self, mediator: Mediator, request: Request[T]) -> T:
        return mediator.provide_from_next(request)


NEXT_PROVIDER = NextProvider()


class LimitingProvider(Provider):
    def __init__(self, req_checker: RequestChecker, provider: Provider):
        self.req_checker = req_checker
        self.provider = provider

        req_checker_rdkw = ClassDispatcherKeysView(
            set(req_checker.get_allowed_request_classes())
        )

        self._rd = provider.get_request_dispatcher().keys().intersect(
            req_checker_rdkw
        ).bind('_lp_proxy_provide')

        super().__init__()

    def get_request_dispatcher(self) -> RequestDispatcher:
        return self._rd

    def _lp_proxy_provide(self, mediator: Mediator, request: Request[T]) -> T:
        self.req_checker(request)
        return self.provider.apply_provider(mediator, request)


def foreign_parser(func: Callable[[Any], T]) -> Parser[T]:
    def foreign_parser_wrapper(arg):
        try:
            return func(arg)
        except PARSER_COMPAT_EXCEPTIONS as e:
            raise ParseError() from e

    return foreign_parser_wrapper


class ValueProvider(Provider, Generic[T]):
    def __init__(self, request_type: Type[Request[T]], value: T):
        self.value = value
        self._rd = RequestDispatcher({request_type: "_provide_value"})

    def get_request_dispatcher(self) -> RequestDispatcher:
        return self._rd

    def _provide_value(self, mediator: Mediator, request: Request):
        return self.value
