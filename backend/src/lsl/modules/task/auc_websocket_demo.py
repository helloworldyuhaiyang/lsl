import json
import time
import uuid
import requests


def submit_task():

    #submit_url = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
    submit_url = "https://openspeech-direct.zijieapi.com/api/v3/auc/bigmodel/submit"

    task_id = str(uuid.uuid4())

    headers = {
        "X-Api-App-Key": appid,
        "X-Api-Access-Key": token,
        "X-Api-Resource-Id": "volc.bigasr.auc",
        "X-Api-Request-Id": task_id,
        "X-Api-Sequence": "-1"
    }

    request = {
        "user": {
            "uid": "fake_uid"
        },
        "audio": {
            "url": file_url,
            "language": "en-US"
            # "format": "mp3",
            # "codec": "map3",
            # "rate": 48000,
            # "bits": 16,
            #"channel": 2
        },
        "request": {
            "model_name": "bigmodel",
            #  ITN 的任务是将 ASR 模型的原始语音输出转换为书面形式，以提高文本的可读性。
            # 例如: 一九七零年->1970年  一百二十三美元->$123
            "enable_itn": True,
            # 启用标点符号
            "enable_punc": True, 
            # 语义顺滑
            "enable_ddc": True, 
            # 启用说话人聚类分离
            "enable_speaker_info": True, 
            # 语音情绪检测
            "enable_emotion_detection": True,
            # 性别检测
            "enable_gender_detection": True,
            "corpus": {
                # "boosting_table_name": "test",
                "correct_table_name": "",
                "context": """{
                    \"context_type\": \"dialog_ctx\",
                    \"context_data\":[
                        {\"text\": \"业务场景信息:这是一个英语口语课的音频文件.\"},
                        {\"text\": \"用户信息: 老师是纽约女性. 学生是杭州男性, 口语速度较慢\"}
                    ]
                }"""
            }
        }
    }
    print(f'Submit task id: {task_id}')
    response = requests.post(submit_url, data=json.dumps(request), headers=headers)
    if 'X-Api-Status-Code' in response.headers and response.headers["X-Api-Status-Code"] == "20000000":
        print(f'Submit task response header X-Api-Status-Code: {response.headers["X-Api-Status-Code"]}')
        print(f'Submit task response header X-Api-Message: {response.headers["X-Api-Message"]}')
        x_tt_logid = response.headers.get("X-Tt-Logid", "")
        print(f'Submit task response header X-Tt-Logid: {response.headers["X-Tt-Logid"]}\n')
        return task_id, x_tt_logid
    else:
        print(f'Submit task failed and the response headers are: {response.headers}')
        exit(1)
    return task_id


def query_task(task_id, x_tt_logid):
    query_url = "https://openspeech-direct.zijieapi.com/api/v3/auc/bigmodel/query"

    headers = {
        "X-Api-App-Key": appid,
        "X-Api-Access-Key": token,
        "X-Api-Resource-Id": "volc.bigasr.auc",
        "X-Api-Request-Id": task_id,
        "X-Tt-Logid": x_tt_logid  # 固定传递 x-tt-logid
    }

    response = requests.post(query_url, json.dumps({}), headers=headers)

    if 'X-Api-Status-Code' in response.headers:
        print(f'Query task response header X-Api-Status-Code: {response.headers["X-Api-Status-Code"]}')
        print(f'Query task response header X-Api-Message: {response.headers["X-Api-Message"]}')
        print(f'Query task response header X-Tt-Logid: {response.headers["X-Tt-Logid"]}\n')
    else:
        print(f'Query task failed and the response headers are: {response.headers}')
        exit(1)
    return response


def main():
    task_id, x_tt_logid = submit_task()
    while True:
        query_response = query_task(task_id, x_tt_logid)
        code = query_response.headers.get('X-Api-Status-Code', "")
        if code == '20000000':  # task finished
            result = query_response.json()
            print(result)
            with open('result.json', 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
            print("SUCCESS!")
            exit(0)
        elif code != '20000001' and code != '20000002':  # task failed
            print("FAILED!")
            exit(1)
        time.sleep(1)

# 需要使用在线url，推荐使用TOS
file_url = "https://other-helloworld.oss-cn-hangzhou.aliyuncs.com/conversation/web_user/0c5bfc47464343e8953c4bb5b129996a.m4a"

# 填入控制台获取的app id和access token
appid = "1805848308"
token = "Bxge8EJzR7jVBuqxG3G_bZGTVMlq40AQ"

if __name__ == '__main__':
    main()
