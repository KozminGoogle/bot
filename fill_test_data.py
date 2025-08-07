# fill_test_data.py
import asyncio
from db import get_session
from models import MasterClass, Slot
from datetime import datetime, timedelta

async def main():
    async for session in get_session():
        # Добавим 3 обычных мастер-класса
        for i in range(1, 4):
            mk = MasterClass(
                title=f"Мастер-класс {i}",
                description=f"Описание мастер-класса {i}",
                photo=None,
                max_people=10,
                is_team=0
            )
            session.add(mk)
            await session.flush()
            # Добавим 2 слота к каждому
            for j in range(2):
                slot = Slot(
                    master_class_id=mk.id,
                    time=datetime.now() + timedelta(days=j, hours=i),
                    max_people=10
                )
                session.add(slot)
        # Добавим 1 командный мастер-класс
        mk_team = MasterClass(
            title="Командный мастер-класс",
            description="Описание командного мастер-класса",
            photo=None,
            max_people=20,
            is_team=1
        )
        session.add(mk_team)
        await session.flush()
        for j in range(2):
            slot = Slot(
                master_class_id=mk_team.id,
                time=datetime.now() + timedelta(days=j, hours=12),
                max_people=5
            )
            session.add(slot)
        await session.commit()

if __name__ == "__main__":
    asyncio.run(main())
