# -*- coding: utf-8 -*-
#__author__ = 'bobby'

from datetime import datetime
from elasticsearch_dsl import Document, Integer, Keyword, Text,analyzer,Completion

from elasticsearch_dsl.analysis import CustomAnalyzer as _CustomAnalyzer

from elasticsearch_dsl.connections import connections
connections.create_connection(hosts=['0,0,0,0'], timeout=20)

from elasticsearch_dsl.analysis import CustomAnalyzer as _CustomAnalyzer
class CustomAnalyzer(_CustomAnalyzer):
    def get_analysis_definition(self):
        return {}


ik_analyzer = CustomAnalyzer("ik_max_word", filter=["lowercase"])

#当查询query时，Elasticsearch会根据搜索类型决定是否对query进行analyze，然后和倒排索引中的term进行相关性查询，匹配相应的文档。
class commodityType(Document):
    cmdt_num = Text(analyzer=ik_analyzer)
    cmdt_name = Text(analyzer=ik_analyzer)
    cmdt_name_completion = Completion(analyzer=ik_analyzer)

    cmdt_name_ckip_final = Text(analyzer='whitespace')
    description_ckip_final = Text(analyzer='whitespace')

    class Index:
        name = 'commodity'


class commodityType_down(Document):  # 類型
    cmdt_num = Text(analyzer=ik_analyzer)  # 放入的文本被ik
    cmdt_name = Text(analyzer=ik_analyzer)
    cmdt_name_completion = Completion(analyzer=ik_analyzer)

    cmdt_name_ckip_final = Text(analyzer='whitespace')

    class Index:
        name = 'commodity_down'  # commodity_down

if __name__ == "__main__":
    commodityType.init()
    commodityType_down.init()
