from funasr import AutoModel
# model = AutoModel(model="paraformer-zh-streaming", model_revision="v2.0.4", disable_update=True,device="cuda:0")
model  = AutoModel(model="./model", model_revision="v2.0.4", disable_update=True,device="cuda:0")

wav_file = f"audio.wav"
res = model.generate(input=wav_file)

print(res)