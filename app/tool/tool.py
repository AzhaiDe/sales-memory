from autogen_core.tools import FunctionTool

from app.tool.good import search_goods
from app.tool.ybx_contact_info import get_contact_info_ybx
from app.tool.ybx_order_info import get_order_info_ybx
from app.tool.ybx_query import get_info_ybx

search_goods_tool = FunctionTool(search_goods, name="search_goods",
                                 description="查询商品详情，以获取规格，适用症状，功效，使用方式等信息")

tools = {
    "get_order_info_ybx": get_order_info_ybx,
    "get_contact_info_ybx": get_contact_info_ybx,
    "get_info_ybx": get_info_ybx
}
