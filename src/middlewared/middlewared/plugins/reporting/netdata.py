from asyncio.exceptions import TimeoutError

from aiohttp import ClientSession

from middlewared.service import CallError


DP = 19999
DBI = '127.0.0.1'
DAU = 'api/v1'
BURL = f'http://{DBI}:{DP}/{DAU}'
REQ_TIMEOUT = 30  # seconds
METRICS_ENDPOINT = 'data?chart={chart}&before={before}&after={after}'


class NetData():

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_t, exc_v, exc_tb):
        if exc_t is not None:
            raise

    async def format_error(self, response):
        return f'with status: [{response.status!r}] with reason: {response.reason!r}'

    async def make_request(self, resource, timeout=REQ_TIMEOUT):
        resource = resource.removeprefix('/')
        async with ClientSession() as sess:
            try:
                res = await sess.get(f'{BURL}/{resource}', timeout=timeout)
            except TimeoutError:
                raise CallError('Timed out waiting on a response')
            else:
                if res.status != 200:
                    raise CallError(f'Failed to get data {await self.format_error(res)}')

            try:
                return res.json()
            except Exception as e:
                raise CallError(f'Failed to json decode response: {e!r}')

    async def get_info(self):
        """Get information about the running netdata instance"""
        return await self.make_request('info')

    async def get_all_metrics(self):
        return await self.make_request('allmetrics?format=json')

    async def get_charts(self):
        """Get available charts"""
        return list((await self.make_request('charts')).get('charts', {}))

    async def get_chart_details(self, chart):
        """Get details for `chart`"""
        return (await self.make_request('charts')).get('charts', {}).get(chart, {})

    async def get_chart_metrics(self, chart, before=None, after=None):
        """Get metrics for `chart`"""
        before = 0 if before is None else before
        after = -1 if after is None else after
        url = METRICS_ENDPOINT.format(chart=chart, before=before, after=after)
        return await self.make_request(url)
