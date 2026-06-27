import asyncio
from api.main import lifespan, app, predict_full_race

async def test():
    async with lifespan(app):
        try:
            res = predict_full_race(2026, 10)
            print("BARCELONA 2026 PREDICTIONS:")
            print([(d.driver_id, d.constructor_id, d.p1_probability, d.position) for d in res.full_grid])
        except Exception as e:
            print("Error:", e)

asyncio.run(test())
