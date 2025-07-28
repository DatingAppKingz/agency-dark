"""
Distributed tracing with OpenTelemetry
"""
import os
import functools
from typing import Dict, Any, Optional, Callable
from contextlib import contextmanager

from opentelemetry import trace, baggage, context
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.zipkin import ZipkinExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor
)
from opentelemetry.trace import Status, StatusCode
from opentelemetry.propagate import set_global_textmap
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.propagators.composite import CompositePropagator

from core.config import settings
from core.logging import logger


# Tracer configuration
class TracingConfig:
    """Tracing configuration"""
    
    def __init__(self):
        self.enabled = getattr(settings, 'TRACING_ENABLED', True)
        self.service_name = getattr(settings, 'SERVICE_NAME', 'agency-backend')
        self.service_version = getattr(settings, 'APP_VERSION', '1.0.0')
        self.environment = getattr(settings, 'ENVIRONMENT', 'production')
        self.exporter_type = getattr(settings, 'TRACE_EXPORTER', 'otlp')  # otlp, jaeger, zipkin
        self.otlp_endpoint = getattr(settings, 'OTLP_ENDPOINT', 'localhost:4317')
        self.jaeger_endpoint = getattr(settings, 'JAEGER_ENDPOINT', 'localhost:14268')
        self.zipkin_endpoint = getattr(settings, 'ZIPKIN_ENDPOINT', 'http://localhost:9411/api/v2/spans')
        self.sample_rate = getattr(settings, 'TRACE_SAMPLE_RATE', 1.0)
        self.debug = getattr(settings, 'TRACE_DEBUG', False)


config = TracingConfig()


class TracingService:
    """Main tracing service"""
    
    def __init__(self, config: TracingConfig):
        self.config = config
        self.tracer_provider = None
        self.tracer = None
        self._instrumentors = []
    
    def initialize(self):
        """Initialize tracing"""
        if not self.config.enabled:
            logger.info("Tracing is disabled")
            return
        
        # Create resource
        resource = Resource.create({
            SERVICE_NAME: self.config.service_name,
            SERVICE_VERSION: self.config.service_version,
            "service.environment": self.config.environment,
            "service.instance.id": os.getenv("HOSTNAME", "unknown"),
            "telemetry.sdk.language": "python",
            "telemetry.sdk.name": "opentelemetry",
        })
        
        # Create tracer provider
        self.tracer_provider = TracerProvider(resource=resource)
        
        # Add span processors
        if self.config.debug:
            self.tracer_provider.add_span_processor(
                SimpleSpanProcessor(ConsoleSpanExporter())
            )
        
        # Add main exporter
        exporter = self._create_exporter()
        if exporter:
            self.tracer_provider.add_span_processor(
                BatchSpanProcessor(exporter)
            )
        
        # Set global tracer provider
        trace.set_tracer_provider(self.tracer_provider)
        
        # Set propagators
        set_global_textmap(
            CompositePropagator([
                TraceContextTextMapPropagator(),
                W3CBaggagePropagator()
            ])
        )
        
        # Get tracer
        self.tracer = trace.get_tracer(
            self.config.service_name,
            self.config.service_version
        )
        
        logger.info(f"Tracing initialized with {self.config.exporter_type} exporter")
    
    def _create_exporter(self):
        """Create span exporter based on configuration"""
        try:
            if self.config.exporter_type == 'otlp':
                return OTLPSpanExporter(
                    endpoint=self.config.otlp_endpoint,
                    insecure=True
                )
            elif self.config.exporter_type == 'jaeger':
                return JaegerExporter(
                    agent_host_name=self.config.jaeger_endpoint.split(':')[0],
                    agent_port=int(self.config.jaeger_endpoint.split(':')[1]) if ':' in self.config.jaeger_endpoint else 6831,
                    collector_endpoint=f"http://{self.config.jaeger_endpoint}/api/traces"
                )
            elif self.config.exporter_type == 'zipkin':
                return ZipkinExporter(
                    endpoint=self.config.zipkin_endpoint
                )
            else:
                logger.warning(f"Unknown exporter type: {self.config.exporter_type}")
                return None
        except Exception as exc:
            logger.error(f"Failed to create exporter: {exc}")
            return None
    
    def instrument_app(self, app):
        """Instrument FastAPI application"""
        if not self.config.enabled:
            return
        
        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=self.tracer_provider,
            excluded_urls="/metrics,/health"
        )
        self._instrumentors.append(FastAPIInstrumentor())
        
        logger.info("FastAPI instrumented for tracing")
    
    def instrument_sqlalchemy(self, engine):
        """Instrument SQLAlchemy"""
        if not self.config.enabled:
            return
        
        SQLAlchemyInstrumentor().instrument(
            engine=engine,
            tracer_provider=self.tracer_provider
        )
        self._instrumentors.append(SQLAlchemyInstrumentor())
        
        logger.info("SQLAlchemy instrumented for tracing")
    
    def instrument_redis(self):
        """Instrument Redis"""
        if not self.config.enabled:
            return
        
        RedisInstrumentor().instrument(
            tracer_provider=self.tracer_provider
        )
        self._instrumentors.append(RedisInstrumentor())
        
        logger.info("Redis instrumented for tracing")
    
    def instrument_celery(self):
        """Instrument Celery"""
        if not self.config.enabled:
            return
        
        CeleryInstrumentor().instrument(
            tracer_provider=self.tracer_provider
        )
        self._instrumentors.append(CeleryInstrumentor())
        
        logger.info("Celery instrumented for tracing")
    
    def instrument_http_clients(self):
        """Instrument HTTP clients"""
        if not self.config.enabled:
            return
        
        # Instrument requests
        RequestsInstrumentor().instrument(
            tracer_provider=self.tracer_provider
        )
        self._instrumentors.append(RequestsInstrumentor())
        
        # Instrument httpx
        HTTPXClientInstrumentor().instrument(
            tracer_provider=self.tracer_provider
        )
        self._instrumentors.append(HTTPXClientInstrumentor())
        
        logger.info("HTTP clients instrumented for tracing")
    
    def shutdown(self):
        """Shutdown tracing"""
        if self.tracer_provider:
            self.tracer_provider.shutdown()
        
        # Uninstrument all
        for instrumentor in self._instrumentors:
            try:
                instrumentor.uninstrument()
            except:
                pass


# Global tracing service
tracing_service = TracingService(config)


# Context managers and decorators
@contextmanager
def trace_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL
):
    """Context manager for creating spans"""
    if not tracing_service.tracer:
        yield None
        return
    
    with tracing_service.tracer.start_as_current_span(
        name,
        kind=kind,
        attributes=attributes or {}
    ) as span:
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise


def trace_method(
    name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL
):
    """Decorator for tracing methods"""
    def decorator(func):
        span_name = name or f"{func.__module__}.{func.__name__}"
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with trace_span(span_name, attributes, kind) as span:
                if span:
                    # Add function arguments as span attributes
                    span.set_attribute("function.args", str(args)[:1000])
                    span.set_attribute("function.kwargs", str(kwargs)[:1000])
                
                result = await func(*args, **kwargs)
                
                if span:
                    span.set_attribute("function.result", str(result)[:1000])
                
                return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with trace_span(span_name, attributes, kind) as span:
                if span:
                    span.set_attribute("function.args", str(args)[:1000])
                    span.set_attribute("function.kwargs", str(kwargs)[:1000])
                
                result = func(*args, **kwargs)
                
                if span:
                    span.set_attribute("function.result", str(result)[:1000])
                
                return result
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def add_span_attributes(attributes: Dict[str, Any]):
    """Add attributes to current span"""
    span = trace.get_current_span()
    if span and span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(key, value)


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Add event to current span"""
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event(name, attributes=attributes or {})


def set_span_status(status_code: StatusCode, description: Optional[str] = None):
    """Set status of current span"""
    span = trace.get_current_span()
    if span and span.is_recording():
        span.set_status(Status(status_code, description))


def get_current_trace_id() -> Optional[str]:
    """Get current trace ID"""
    span = trace.get_current_span()
    if span and span.is_recording():
        span_context = span.get_span_context()
        return format(span_context.trace_id, '032x')
    return None


def get_current_span_id() -> Optional[str]:
    """Get current span ID"""
    span = trace.get_current_span()
    if span and span.is_recording():
        span_context = span.get_span_context()
        return format(span_context.span_id, '016x')
    return None


# Baggage operations
def set_baggage(key: str, value: str):
    """Set baggage value"""
    ctx = baggage.set_baggage(key, value)
    context.attach(ctx)


def get_baggage(key: str) -> Optional[str]:
    """Get baggage value"""
    return baggage.get_baggage(key)


def get_all_baggage() -> Dict[str, str]:
    """Get all baggage"""
    return dict(baggage.get_all())


# Custom span processors
class ErrorAlertSpanProcessor(SpanProcessor):
    """Span processor that alerts on errors"""
    
    def on_start(self, span, parent_context=None):
        pass
    
    def on_end(self, span):
        if span.status.status_code == StatusCode.ERROR:
            # Log error spans
            logger.error(
                f"Error in span {span.name}: {span.status.description}",
                extra={
                    'trace_id': format(span.context.trace_id, '032x'),
                    'span_id': format(span.context.span_id, '016x'),
                    'service': span.resource.attributes.get(SERVICE_NAME),
                    'attributes': dict(span.attributes)
                }
            )
    
    def shutdown(self):
        pass
    
    def force_flush(self, timeout_millis=30000):
        return True


class SlowSpanProcessor(SpanProcessor):
    """Span processor that tracks slow operations"""
    
    def __init__(self, threshold_ms: float = 1000):
        self.threshold_ns = threshold_ms * 1_000_000  # Convert to nanoseconds
    
    def on_start(self, span, parent_context=None):
        pass
    
    def on_end(self, span):
        duration = span.end_time - span.start_time
        if duration > self.threshold_ns:
            duration_ms = duration / 1_000_000
            logger.warning(
                f"Slow span detected: {span.name} took {duration_ms:.2f}ms",
                extra={
                    'trace_id': format(span.context.trace_id, '032x'),
                    'span_id': format(span.context.span_id, '016x'),
                    'duration_ms': duration_ms,
                    'attributes': dict(span.attributes)
                }
            )
    
    def shutdown(self):
        pass
    
    def force_flush(self, timeout_millis=30000):
        return True


# FastAPI integration
from fastapi import FastAPI, Request
import asyncio


def setup_tracing(app: FastAPI):
    """Setup tracing for FastAPI application"""
    
    # Initialize tracing
    tracing_service.initialize()
    
    # Add custom processors
    if tracing_service.tracer_provider:
        tracing_service.tracer_provider.add_span_processor(ErrorAlertSpanProcessor())
        tracing_service.tracer_provider.add_span_processor(SlowSpanProcessor())
    
    # Instrument app
    tracing_service.instrument_app(app)
    
    # Instrument other libraries
    tracing_service.instrument_redis()
    tracing_service.instrument_celery()
    tracing_service.instrument_http_clients()
    
    # Add trace ID to responses
    @app.middleware("http")
    async def add_trace_id_header(request: Request, call_next):
        response = await call_next(request)
        
        trace_id = get_current_trace_id()
        if trace_id:
            response.headers["X-Trace-ID"] = trace_id
        
        return response
    
    # Shutdown hook
    @app.on_event("shutdown")
    async def shutdown_tracing():
        tracing_service.shutdown()


# Example usage patterns
"""
# Basic span creation
with trace_span("process_order", {"order_id": "123"}):
    # Process order
    pass

# Method tracing
@trace_method()
async def fetch_user_data(user_id: str):
    # Fetch data
    pass

# Adding attributes to current span
add_span_attributes({
    "user.id": "123",
    "user.type": "premium"
})

# Adding events
add_span_event("payment_processed", {
    "amount": 100.50,
    "currency": "USD"
})

# Setting span status
try:
    # Some operation
    pass
except Exception as e:
    set_span_status(StatusCode.ERROR, str(e))
    raise

# Using baggage for context propagation
set_baggage("user_id", "123")
user_id = get_baggage("user_id")
"""
