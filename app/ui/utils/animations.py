from typing import Callable, cast
from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
)
from PySide6.QtWidgets import QGraphicsEffect, QGraphicsOpacityEffect, QWidget


def clear_graphics_effect(widget: QWidget) -> None:
    """
    Safely detach and disable QGraphicsEffect to release QWidgetEffectSourcePrivate
    and restore direct native painting without Pylance typing warnings.
    """
    if (effect := widget.graphicsEffect()) is not None:
        effect.setEnabled(False)
    # In Qt C++, setGraphicsEffect(nullptr) explicitly removes the effect.
    # cast() satisfies PySide6 type stubs that omitted Optional[QGraphicsEffect].
    widget.setGraphicsEffect(cast(QGraphicsEffect, None))


def fade_in_widget(
    widget: QWidget,
    duration_ms: int = 180,
    start_opacity: float = 0.0,
    end_opacity: float = 1.0,
    easing: QEasingCurve.Type = QEasingCurve.Type.OutCubic,
    on_finished: Callable[[], None] | None = None,
) -> QPropertyAnimation | None:
    """
    Apply a smooth fade-in opacity animation and release the QGraphicsEffect on completion
    to restore direct native painting and prevent QPainter concurrency collisions.
    """
    if not widget.isVisible():
        widget.show()

    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(start_opacity)
    widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration_ms)
    anim.setStartValue(start_opacity)
    anim.setEndValue(end_opacity)
    anim.setEasingCurve(easing)

    def _cleanup_effect() -> None:
        clear_graphics_effect(widget)
        if on_finished:
            on_finished()

    anim.finished.connect(_cleanup_effect)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def fade_out_widget(
    widget: QWidget,
    duration_ms: int = 130,
    end_opacity: float = 0.0,
    easing: QEasingCurve.Type = QEasingCurve.Type.InCubic,
    on_finished: Callable[[], None] | None = None,
) -> QPropertyAnimation | None:
    """Apply a smooth fade-out opacity animation and cleanup effect on completion."""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration_ms)
    anim.setStartValue(effect.opacity())
    anim.setEndValue(end_opacity)
    anim.setEasingCurve(easing)

    def _cleanup_effect() -> None:
        widget.hide()
        clear_graphics_effect(widget)
        if on_finished:
            on_finished()

    anim.finished.connect(_cleanup_effect)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim