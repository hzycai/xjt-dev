from funasr import AutoModel
model = AutoModel(model="paraformer-zh-streaming", model_revision="v2.0.4", disable_update=True,device="cuda:0")
print("模型加载成功")