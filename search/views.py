import json
from django.shortcuts import render
from django.views.generic.base import View
from search.models import commodityType,commodityType_down
from django.http import HttpResponse
from elasticsearch import Elasticsearch
import pandas as pd
import redis
from datetime import datetime
import random

df_up = pd.read_excel('./電商商品主檔_ckip_for_詞頻_20220803.xlsx')
df_up = df_up[['電商商品代號', '商品名稱', '商品名稱_clean_major_ckip_final', '商品敘述_1_clean_major_ckip_final']]
df_up.drop_duplicates(subset=['商品名稱', '商品名稱_clean_major_ckip_final', '商品敘述_1_clean_major_ckip_final'], inplace=True)
df_up.reset_index(drop=True, inplace=True)
df_up= df_up.set_index(['電商商品代號'])

df_down = pd.read_excel('./down.xlsx')
df_down= df_down.set_index(['商品名稱_clean_major'])


es = Elasticsearch(hosts=["0,0,0,0"]) #serve上的IP-- ipconfig
redis_cli = redis.StrictRedis(host='0,0,0,0', port=6379, db=0)# redis為本地的緩存->結果給大數據

now_time = datetime.now()
class IndexView(View):
    #首页
    def get(self, request):
        topn_search = redis_cli.zrevrangebyscore("search_keywords_set",'+inf', '-inf', withscores=True)
        top = []
        for obj in topn_search:
            keyword, score = obj
            top.append(keyword.decode('utf-8'))
        top = top[:5]
        return render(request, "index.html", {"topn_search":top})

# Create your views here.
class SearchSuggest(View):
    def get(self, request):
        key_words = request.GET.get('s','')
        s_type = request.GET.get("s_type", "article")  # 如果沒有就選"article"

        if key_words:
            if s_type=="article":
                re_datas = []
                re_datas_id = []
                s = commodityType.search()                         #另一個類
                s = s.suggest('my_search', key_words, completion={
                    "field":"cmdt_name_completion", "fuzzy":{
                        "fuzziness":"auto",
                        "prefix_length":1
                    },
                    "size": 10
                })
                response= s.execute()
                for result in response.suggest.my_search:
                    for option in result.options:
                        if option.text not in re_datas:
                            re_datas.append(option.text)
                            re_datas_id.append(option._id)
                #判斷是否有10個 全文字
                # 自身變換  並將變換的值
                if len(re_datas) < 10:
                    temp = []  # 過濾
                    for re_id in re_datas_id:

                        b = eval(df_up.loc[re_id]['商品敘述_1_clean_major_ckip_final'])
                        try:
                            b.index(key_words)
                            if b[b.index(key_words) + 1] not in temp:
                                temp.append(b[b.index(key_words) + 1])

                            re_datas.append(key_words + ' ' + b[b.index(key_words) + 1])
                        except:
                            pass

                        if len(re_datas) == 10:  break
                        try:
                            b.index(key_words)
                            if b[b.index(key_words) + 2] not in temp:
                                temp.append(b[b.index(key_words) + 2])
                            re_datas.append(key_words + ' ' + b[b.index(key_words) + 2])
                        except:
                            pass

                        if len(re_datas) == 10:  break
                return HttpResponse(json.dumps(re_datas), content_type="application/json")
            elif s_type=="question":
                re_datas = []
                re_datas_id = []
                s = commodityType_down.search()  # 另一個類
                s = s.suggest('my_search', key_words, completion={
                    "field": "cmdt_name_completion", "fuzzy": {
                        "fuzziness": "auto",
                        "prefix_length": 1
                    },
                    "size": 10
                })
                response = s.execute()
                for result in response.suggest.my_search:
                    for option in result.options:
                        if option.text not in re_datas:
                            re_datas.append(option.text)
                            re_datas_id.append(option._id)

                # 自身變換  並將變換的值
                if len(re_datas) < 10:
                    random_data=''  # 過濾
                    for re_data in re_datas:
                        try:
                            b = eval(df_down.loc[re_data]['商品名稱_clean_major_ckip_final'])
                            b.remove(key_words)  #取1/2  len(b)
                            random_data=key_words + ' ' + random.choice(b)
                            if random_data not in re_datas:
                                re_datas.append(random_data)


                        except:
                            pass
                        #透過
                        if len(re_datas) == 10:  break

                return HttpResponse(json.dumps(re_datas), content_type="application/json")


class SearchView(View):
    def get(self, request):
        key_words = request.GET.get("q","")
        s_type = request.GET.get("s_type", "article") #如果沒有就選"article"
        redis_cli.zincrby("search_keywords_set", 1, key_words)
        topn_search = redis_cli.zrevrangebyscore("search_keywords_set", '+inf', '-inf', withscores=True)
        top = []
        for obj in topn_search:
            keyword, score = obj
            top.append(keyword.decode('utf-8'))
        top = top[:5]
        if s_type=="article":
            #判斷s_type
            page = request.GET.get("p", "1")
            try:
                page = int(page)
            except:
                page = 1

            #jobbole_count = redis_cli.get("jobbole_count")#記錄在redis
            start_time = datetime.now()

            response = es.search(
                index= "commodity",
                body={

                      "query": {
                        "bool": {
                          "should": [
                            {
                              "match_phrase": {
                                "cmdt_name": key_words
                              }
                            },
                            {
                              "match": {
                                "cmdt_name_ckip_final": key_words
                              }
                            },
                            {
                              "match": {
                                "description_ckip_final": key_words
                              }
                            }
                          ]
                        }
                      },
                    "from":(page-1)*10,
                    "size":10,

                }
            )

            end_time = datetime.now()
            last_seconds = (end_time-start_time).total_seconds()
            total_nums = response["hits"]["total"]['value']
            if (page%10) > 0:
                page_nums = int(total_nums/10) +1
            else:
                page_nums = int(total_nums/10)

            hit_list = []
            for hit in response["hits"]["hits"]:#結果
                hit_dict = {}

                temp=hit['_source']["cmdt_num"]
                hit_dict["content"] =temp+'<br>'+ hit["_source"]["cmdt_name"][:500] #"".join(hit["_source"]["cmdt_name"])[:500]
                hit_dict["score"] = hit["_score"]

                hit_list.append(hit_dict)

            jobbole_count = total_nums
            return render(request, "result.html", {"page":page,
                                                   "all_hits":hit_list,
                                                   "key_words":key_words,
                                                   "total_nums":total_nums,
                                                   "page_nums":page_nums,
                                                   "last_seconds":last_seconds,
                                                   "jobbole_count":jobbole_count,
                                                   'year':now_time.year,
                                                   'month':now_time.month,
                                                   "topn_search":top})
        elif s_type=="question":


            page = request.GET.get("p", "1")
            try:
                page = int(page)
            except:
                page = 1

            # jobbole_count = redis_cli.get("jobbole_count")#記錄在redis
            start_time = datetime.now()

            response = es.search(
                index="commodity_down",
                body={

                    "query": {
                        "bool": {
                            "should": [
                                {
                                    "match_phrase": {
                                        "cmdt_name": key_words
                                    }
                                },
                                {
                                    "match": {
                                        "cmdt_name_ckip_final": key_words
                                    }
                                }
                            ]
                        }
                    },
                    "from": (page - 1) * 10,
                    "size": 10,

                }
            )

            end_time = datetime.now()
            last_seconds = (end_time - start_time).total_seconds()
            total_nums = response["hits"]["total"]['value']
            if (page % 10) > 0:
                page_nums = int(total_nums / 10) + 1
            else:
                page_nums = int(total_nums / 10)

            hit_list = []
            for hit in response["hits"]["hits"]:  # 結果
                hit_dict = {}

                temp = hit['_source']["cmdt_num"]
                hit_dict["content"] = temp + '<br>' + hit["_source"]["cmdt_name"][
                                                      :500]  # "".join(hit["_source"]["cmdt_name"])[:500]
                hit_dict["score"] = hit["_score"]

                hit_list.append(hit_dict)

            jobbole_count = total_nums
            return render(request, "result.html", {"page": page,
                                                   "all_hits": hit_list,
                                                   "key_words": key_words,
                                                   "total_nums": total_nums,
                                                   "page_nums": page_nums,
                                                   "last_seconds": last_seconds,
                                                   "jobbole_count": jobbole_count,
                                                   'year': now_time.year,
                                                   'month': now_time.month,
                                                   "topn_search": top})

    '''分詞後 全文檢索
        "query":{
            "multi_match":{
                "query":key_words, #空格就是多詞查詢
                "type": "most_fields",
                #"fields": ["cmdt_name_ckip_final", "description_ckip_final"]              #精準["cmdt_name_ckip_final", "description_ckip_final"]
                "fields":["cmdt_name","cmdt_name_ckip_final", "description_ckip_final"]  #"cmdt_name"搜索字與文本都ik  重複一次強化權重  敘述包含比較多採用精準
            }

        },
    '''
