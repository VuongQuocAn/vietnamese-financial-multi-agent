"""Web adapter for an injected, approved-data conversation service."""

from fastapi import APIRouter, HTTPException

from .conversations import ConversationMessage, ConversationState, ConversationTurn


def conversation_router(service):
    router = APIRouter(prefix="/api/conversations", tags=["conversations"])

    def configured():
        if service is None:
            raise HTTPException(503, "conversation_service_not_configured")
        return service

    @router.post("", response_model=ConversationState, status_code=201)
    def create_conversation():
        return configured().create()

    @router.get("/{conversation_id}", response_model=ConversationState)
    def conversation_history(conversation_id: str):
        try:
            return configured().history(conversation_id)
        except KeyError:
            raise HTTPException(404, "conversation_not_found") from None

    @router.post("/{conversation_id}/messages", response_model=ConversationTurn)
    def send_message(conversation_id: str, request: ConversationMessage):
        try:
            return configured().send(conversation_id, request)
        except KeyError:
            raise HTTPException(404, "conversation_not_found") from None

    return router
