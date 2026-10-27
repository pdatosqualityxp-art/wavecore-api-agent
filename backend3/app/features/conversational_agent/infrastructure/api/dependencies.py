from fastapi import Request

from app.features.conversational_agent.application.agent import ConversationalAgent


def get_conversational_agent(request: Request) -> ConversationalAgent:
    agent: ConversationalAgent = request.app.state.conversational_agent
    return agent
