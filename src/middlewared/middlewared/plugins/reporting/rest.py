from middlewared.service import accepts, Service, filterable
from middlewared.utils import filter_list
from middlewared.schema import Str, Dict, Int

from . import NetData


class ReportingRestService(Service):

    class Config:
        private = True
        namespace = 'reporting.rest'

    @filterable
    async def get_charts(self, filters, options):
        async with NetData() as nd:
            return filter_list((await nd.get_charts()).keys(), filters, options)

    @accepts(Str('chart', required=True))
    async def get_chart_details(self, chart):
        async with NetData() as nd:
            return await nd.get_chart_details(chart)

    @accepts(Dict(
        Str('chart', required=True),
        Int('before', required=False, default=0),
        Int('after', required=False, default=-1),
    ))
    async def get_chart_metrics(self, data):
        async with NetData() as nd:
            return await nd.get_chart_metrics(data['chart'], data['before'], data['after'])
