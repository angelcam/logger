import asyncio
import unittest

from ..sinks.executor import AsyncQueue, collect_batch


class CollectBatchTest(unittest.IsolatedAsyncioTestCase):

    async def test_collects_all(self):
        queue = AsyncQueue()
        for record in (b'aaa', b'bbb', b'ccc'):
            queue.push_back(record)

        batch = await collect_batch(queue, max_size=4000000)

        self.assertEqual(batch, [b'aaa', b'bbb', b'ccc'])

    async def test_size_limit(self):
        queue = AsyncQueue()
        for record in (b'aaaa', b'bbbb', b'cc'):
            queue.push_back(record)
        batch = await collect_batch(queue, max_size=10)

        self.assertEqual(batch, [b'aaaa', b'bbbb'])
        self.assertEqual(len(queue), 1)

    async def test_oversized_record(self):
        queue = AsyncQueue()
        queue.push_back(b'aaaaaaaaaaaa')
        queue.push_back(b'b')

        batch = await collect_batch(queue, max_size=10)

        self.assertEqual(batch, [b'aaaaaaaaaaaa'])
        self.assertEqual(len(queue), 1)

    async def test_waits_when_empty(self):
        queue = AsyncQueue()
        collecting = asyncio.ensure_future(collect_batch(queue, max_size=100))

        await asyncio.sleep(0.05)
        self.assertFalse(collecting.done(), 'returned an empty batch')

        queue.push_back(b'late')

        self.assertEqual(await asyncio.wait_for(collecting, 1), [b'late'])
