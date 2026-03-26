from funasr import AutoModel
model = AutoModel(model='iic/SenseVoiceSmall')
res = model.generate(input='data/audio/BV1h4XpBmEMo.wav')
print(res[0]['text'])



#   "funasr",
#   "torch",
#    "modelscope",
#    "torchaudio"