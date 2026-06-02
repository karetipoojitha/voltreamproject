from agent import router as agent_router
from routers import devices, billing, analytics, profile, chat, schedule

def include_routers(app):
    app.include_router(agent_router, prefix="/api/v1", tags=["Agent"])
    app.include_router(devices.router, tags=["Devices"])
    app.include_router(billing.router, tags=["Billing"])
    app.include_router(analytics.router, tags=["Analytics"])
    app.include_router(profile.router, tags=["Profile"])
    app.include_router(chat.router, tags=["Chat & QA"])
    app.include_router(schedule.router, tags=["Schedules"])
