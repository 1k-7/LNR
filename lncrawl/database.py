import motor.motor_asyncio

class Database:
    def __init__(self, mongo_uri):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
        self.db = self.client.lightnovel_bot

    async def get_user_settings(self, chat_id):
        return await self.db.user_settings.find_one({"chat_id": chat_id})

    async def save_user_settings(self, chat_id, settings):
        await self.db.user_settings.update_one(
            {"chat_id": chat_id},
            {"$set": settings},
            upsert=True
        )