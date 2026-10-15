from typing import Optional, Annotated


async def search_goods(good_id: Optional[str | int], good_name: Annotated[str, "商品名称"]) -> Annotated[str, "商品详情"]:
    """
    查询商品详情
    :param good_id: 商品的唯一 id
    :param good_name: 商品的名称
    :return: 当前商品的详细信息
    """
    res: str = "SEARCH GOODS"
    print("-search goods-, good_id={}, good_name={}, result={}".format(good_id, good_name, res))
    return res
