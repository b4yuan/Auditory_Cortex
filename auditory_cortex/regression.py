from pyexpat import features
import numpy as np
import torch
import os
from scipy import linalg
from transformers import Speech2TextForConditionalGeneration, Speech2TextProcessor
from sklearn.linear_model import Ridge

from auditory_cortex.dataset import Neural_Data
from auditory_cortex.feature_extractors import Feature_Extractor_S2T
from auditory_cortex.feature_extractors import Feature_Extractor_GRU
#from sklearn.decomposition import PCA
# import rnn_model.speech_recognition as speech_recognition

# from Dataset import Neural_Data
# from Feature_Extractors import Feature_Extractor_S2T
# from sklearn.decomposition import PCA

import matplotlib.pyplot as plt
import torchaudio

class transformer_regression:
	def __init__(self, dir, subject, model='transformer'):
		self.dir = os.path.join(dir, subject)
		self.dataset = Neural_Data(dir, subject)
		self.model_name = model

		if self.model_name == 'transformer':        
			self.layers = ["model.encoder.conv.conv_layers.0","model.encoder.conv.conv_layers.1","model.encoder.layers.0.fc2",
							"model.encoder.layers.1.fc2","model.encoder.layers.2.fc2","model.encoder.layers.3.fc2",
							"model.encoder.layers.4.fc2","model.encoder.layers.5.fc2","model.encoder.layers.6.fc2",
							"model.encoder.layers.7.fc2","model.encoder.layers.8.fc2","model.encoder.layers.9.fc2"]
			self.model = Speech2TextForConditionalGeneration.from_pretrained("facebook/s2t-small-librispeech-asr")
			self.processor = Speech2TextProcessor.from_pretrained("facebook/s2t-small-librispeech-asr")
			self.model_extractor = Feature_Extractor_S2T(self.model, self.layers)
			# print("Objects created, now loading Transformer layer features...!")
			# self.features, self.demean_features = self.get_transformer_features()
			self.get_transformer_features()
			self.simply_spikes()															

    	# else:
		# 	self.layers = ['birnn_layers.0.BiGRU','birnn_layers.1.BiGRU','birnn_layers.2.BiGRU','birnn_layers.3.BiGRU','birnn_layers.4.BiGRU']
		# 	self.model = speech_recognition.SpeechRecognitionModel(3,5,512,29,128,2,0.1)
		# 	path = os.path.join(dir, 'rnn_model')
		# 	weights_file = "epoch_250.pt"
		# 	checkpoint = torch.load(os.path.join(path,weights_file),map_location=torch.device('cpu'))
		# 	self.model.load_state_dict(checkpoint['state_dict'])
		# 	self.model_extractor = Feature_Extractor_GRU(self.model, self.layers)
		# 	self.spect = torchaudio.transforms.MelSpectrogram(sample_rate=16000, n_mels=128)
		# 	self.features, self.demean_features = self.get_transformer_features()
    



	# def simply_spikes(self, sent_list=[12], ch=0, w = 40, delay=0,  offset=0.39):
	# 	spikes ={}
	# 	for x,i in enumerate(sent_list):
	# 		spikes[i] = torch.tensor(self.dataset.retrieve_spike_counts(sent=i,win=w,delay=delay,early_spikes=False,model=self.model_name,
	# 																offset=offset)[ch])
	# 	# self.spikes_dict = spikes															
	# 	spikes = torch.cat([spikes[i] for i in sent_list], dim = 0).numpy()
	# 	return spikes
	
	def simply_spikes(self, delay=0):
		spikes = [{}, {}]
	
		for i in range(1,500):
			spikes[0][i] = self.dataset.retrieve_spike_counts(sent=i, win=20, delay=delay, 
																early_spikes=False,
																model=self.model_name, 
																offset=-0.25)
			spikes[1][i] = self.dataset.retrieve_spike_counts(sent=i, win=40, delay=delay, 
																early_spikes=False,
																model=self.model_name,
																offset=0.39)

		self.spikes_dict = spikes															
		# spikes = torch.cat([spikes[i] for i in sent_list], dim = 0).numpy()
		# return spikes

	def all_channel_spikes(self, sent_s=1, sent_e=500, w = 40, delay=0,  offset=0.39):
		spikes = []
		result = {}
		for i in range(sent_s,sent_e):
			spikes.append(self.dataset.retrieve_spike_counts(sent=i,win=w,delay=delay,early_spikes=False,model=self.model_name,offset=offset))
		for ch in range(self.dataset.num_channels):
			result[ch] = np.concatenate([spikes[i][ch] for i in range(len(spikes))], axis=0)

		return result

	def demean_spikes(self, sent_s=1, sent_e=500, ch=0, w = 40):
		spikes ={}
		spk_mean = {}
		for x,i in enumerate(range(sent_s,sent_e)):
			spikes[x] = torch.tensor(self.dataset.retrieve_spike_counts(sent=i, win=w ,early_spikes=False)[ch])
			spk_mean[x] = torch.mean(spikes[x], dim = 0)
			spikes[x] = spikes[x] - spk_mean[x]
		
		spikes = torch.cat([spikes[i] for i in range(sent_e - sent_s)], dim = 0).numpy()
		return spikes



	def benchmark_r2_score(self, w = 40, sent = 12):
		#These sentences have repeated trials...!
		#sents = [12,13,32,43,56,163,212,218,287,308]
		r2_scores = np.zeros(self.dataset.num_channels)
		#trials = obj.dataset.get_trials(13)
		spkk = self.dataset.retrieve_spike_counts_for_all_trials(sent=sent, w=w)
	
		for i in range(self.dataset.num_channels):
			h1 = np.mean(spkk[i][0:6], axis=0)
			h2 = np.mean(spkk[i][6:], axis=0)
			r2_scores[i] = self.r2(h1,h2)
		return r2_scores

	def prepare_GRU_input(self, aud):
		aud = aud.astype(np.float32) 
		input = torch.tensor(aud)
		aud_spect = self.spect(input)
		aud_spect = aud_spect.unsqueeze(dim=0)
		aud_spect = aud_spect.unsqueeze(dim=0).type(torch.float32)
		return aud_spect
		
	def translate(self, aud, fs = 16000):
		if self.model_name == 'transformer':
			inputs_features = self.processor(aud,padding=True, sampling_rate=fs, return_tensors="pt").input_features
			generated_ids = self.model_extractor(inputs_features)
		else:
			inputs_features = self.prepare_GRU_input(aud)
			generated_ids = self.model_extractor(inputs_features)

	# def simply_stack(self, features):
	#   features = torch.cat([features[i] for i in range(498)], dim=0)
	#   return features

	# def get_transformer_features(self):
	#   sent_s = 1
	#   sent_e = 499
	#   features = [{} for _ in range(len(self.layers))]

	#   feats = {}
	#   for x, i in enumerate(range(sent_s, sent_e)):
	#     self.translate(self.dataset.audio(i))
	#     for j, l in enumerate(self.layers):
	#       features[j][x] = self.model_extractor.features[l]
		
	#   for j, l in enumerate(self.layers):
	#     feats[j] = torch.cat([features[j][i] for i in range(sent_e-sent_s)], dim=0).numpy()
	#   return feats

	def get_transformer_features(self):
		
		features = [{} for _ in range(len(self.layers))]
		demean_features = [{} for _ in range(len(self.layers))]
		f_mean = {}

		for i in range(1,500):
			self.translate(self.dataset.audio(i))
			for j, l in enumerate(self.layers):
				features[j][i] = self.model_extractor.features[l].squeeze(dim=0)

				# f_mean[i] = torch.mean(features[j][i], dim = 0)    
				# demean_features[j][i]= features[j][i] - f_mean[i]
			# for j, l in enumerate(self.layers):
			# 	if j<2:
			# 		d = 1
			# 	else:
			# 		d=0
		
		self.all_features = features

				# feats[j] = torch.cat([features[j][i] for i in range(len(sent_list))], dim=d).detach().numpy()
				# demean_feats[j] = torch.cat([demean_features[j][i] for i in range(len(sent_list))], dim=d).detach().numpy()
		# return feats, demean_feats


		# self.features = feats
		# self.demean_features = demean_feats

	# for i in range(498):
	#   f_mean[i] = torch.mean(features[i], dim = 0)
	#   features[i] = features[i] - f_mean[i]
	# features = torch.cat([features[i] for i in range(498)], dim=0)

	def down_sample_features(self, feats, k):
		out = np.zeros((int(np.ceil(feats.shape[0]/k)),feats.shape[1]))
		# print(out.shape)
		for i in range(out.shape[0]):
		#Just add the remaining samples at the end...!
			if (i == out.shape[0] -1):
				out[i] = feats[k*i:, :].sum(axis=0)
			else:  
				out[i] = feats[k*i:k*(i+1), :].sum(axis=0)
		return out

	def down_sample_spikes(self, spks, k):
		# out = np.zeros(int(np.ceil(spks.shape[0]/k)))
		out = np.zeros((int(np.ceil(spks.shape[0]/k)), spks.shape[1]))
		for i in range(out.shape[0]):
		#Just add the remaining samples at the end...!
			if (i == out.shape[0] -1):
				out[i] = spks[k*i:, :].sum(axis=0)
			else:  
				out[i] = spks[k*i:k*(i+1), :].sum(axis=0)
		return out

	def compute_r2(self, layer, win):
		k = int(win/40)    # 40 is the min, bin size for 'Speech2Text' transformer model 
		# print(f"k = {k}")
		r2t = np.zeros(self.dataset.num_channels)
		r2v = np.zeros(self.dataset.num_channels)
		pct = np.zeros(self.dataset.num_channels)
		pcv = np.zeros(self.dataset.num_channels)

		#downsamples if k>1 
		if k >1:
			feats = self.down_sample_features(self.features[layer], k)
		else:
			feats = self.features[layer]

		m = int(feats.shape[0] *0.75)
		x_train = feats[0:m, :]
		x_test = feats[m:, :]
		
		for i in range(self.dataset.num_channels):
			y = self.simply_spikes(ch=i)
			if k>1:
				y = self.down_sample_spikes(y,k)
			y_train = y[0:m]
			y_test = y[m:]
			B = self.regression_param(x_train, y_train)
		
			r2t[i] = self.regression_score(x_train, y_train, B)
			r2v[i] = self.regression_score(x_test, y_test, B)
			pct[i] = (np.corrcoef(self.predict(x_train, B), y_train)[0,1])**2
			pcv[i] = (np.corrcoef(self.predict(x_test, B), y_test)[0,1])**2
		return r2t, r2v, pct, pcv



	def compute_r2_channel(self, layer, win, channel, delay):
		k = int(win/40)    # 40 is the min, bin size for 'Speech2Text' transformer model 
		print(f"k = {k}")
		
		# print(f"k = {k}")
		r2t = np.zeros(1)
		r2v = np.zeros(1)
		r2tt = np.zeros(1)
		pct = np.zeros(1)
		pcv = np.zeros(1)
		pctt = np.zeros(1)

		#downsamples if k>1 
		if k >1:
			feats = self.down_sample_features(self.features[layer], k)
		else:
			feats = self.features[layer]

		y = self.simply_spikes(ch=channel, delay=delay)
		if k>1:
			y = self.down_sample_spikes(y,k)

		m = int(feats.shape[0])
		n2 = int(m*0.9)
		x_test = feats[n2:, :]
		y_test = y[n2:]    
		
		for i in range(5):
			a = int(i*0.2*n2)
			b = int((i+1)*0.2*n2)
			
			x_val = feats[a:b, :] 
			y_val = y[a:b] 
			
			x_train = np.concatenate((feats[:a,:], feats[b:n2,:]), axis=0)
			y_train = np.concatenate((y[:a], y[b:n2]))
			# Linear Regression...!
			B = self.regression_param(x_train, y_train)
			y_hat_train = self.predict(x_train, B)
			y_hat_val = self.predict(x_val, B)
			y_hat_test = self.predict(x_test, B)
			
			pct += np.corrcoef(y_hat_train, y_train)[0,1]
			pcv += np.corrcoef(y_hat_val, y_val)[0,1]
			pctt += np.corrcoef(y_hat_test, y_test)[0,1]
			
		pct /= 5
		pcv /= 5
		pctt /= 5
		
		return pct, pcv,pctt
	def get_cc_norm_layer(self, layer, win, delay=0):
		print(f"Computing correlations for layer:{layer} ...")
		num_channels = self.dataset.num_channels
		train_cc_norm = np.zeros(num_channels)
		val_cc_norm = np.zeros(num_channels)
		test_cc_norm = np.zeros(num_channels)
		
		feats, spikes = self.get_feats_and_spikes(layer, win, delay)
	
		for ch in range(num_channels):
			sp = self.dataset.signal_power(win, ch)
			train_cc_norm[ch], val_cc_norm[ch], test_cc_norm[ch] = self.compute_cc_norm(feats, spikes[ch], sp)
			
		return train_cc_norm, val_cc_norm, test_cc_norm
	
	def get_feats_and_spikes(self, layer, win, delay=0):
		if self.model_name=='transformer':
			#def_w = 20
			# offset is used to match different rounding error in 1st conv layer vs the rest of the layers...!
			if layer <1:
				feats = self.features[layer].transpose()
				offset = -0.25
				def_w = 20 
			elif layer < 2:
				feats = self.features[layer].transpose()
				def_w = 40
				offset = 0.39
			else:
				feats = self.features[layer]
				def_w = 40
				offset = 0.39
		else:
			def_w = 25
			
		k = int(win/def_w)    # 40 is the min, bin size for 'Speech2Text' transformer model 
		#print(f"k = {k}")
		r2t = np.zeros(1)
		r2v = np.zeros(1)
		r2tt = np.zeros(1)
		#downsamples if k>1 
		if k >1:
			feats = self.down_sample_features(feats, k)
		
		spikes = self.all_channel_spikes(delay=delay, w = def_w, offset=offset)
		if k>1:
			for ch in range(self.dataset.num_channels):
				spikes[ch] = self.down_sample_spikes(spikes[ch],k)

		return feats, spikes

	def get_cc_norm(self, layer, win, channel, delay=0, alpha=1.0):
		if self.model_name=='transformer':
			#def_w = 20
			# offset is used to match different rounding error in 1st conv layer vs the rest of the layers...!
			if layer <1:
				feats = self.features[layer].transpose()
				offset = -0.25
				def_w = 20 
			elif layer < 2:
				feats = self.features[layer].transpose()
				def_w = 40
				offset = 0.39
			else:
				feats = self.features[layer]
				def_w = 40
				offset = 0.39
		else:
			def_w = 25
			
		k = int(win/def_w)    # 40 is the min, bin size for 'Speech2Text' transformer model 
		# print(f"k = {k}")
		r2t = np.zeros(1)
		r2v = np.zeros(1)
		r2tt = np.zeros(1)
		#downsamples if k>1 
		if k >1:
			feats = self.down_sample_features(feats, k)
		
		y = self.simply_spikes(ch=channel, delay=delay, w = def_w, offset=offset)
		if k>1:
			y = self.down_sample_spikes(y,k)
		
		m = int(feats.shape[0])
		n2 = int(m*0.9)
		x_test = feats[n2:, :]
		y_test = y[n2:]    
		
		# signal power, will be used for normalization
		# sp = self.dataset.signal_power(win, channel)
		sp = 1
		for i in range(5):
			a = int(i*0.2*n2)
			b = int((i+1)*0.2*n2)
			
			x_val = feats[a:b, :] 
			y_val = y[a:b] 
			
			x_train = np.concatenate((feats[:a,:], feats[b:n2,:]), axis=0)
			y_train = np.concatenate((y[:a], y[b:n2]))
			
			# Linear Regression...!
			B = self.regression_param(x_train, y_train)
			y_hat_train = self.predict(x_train, B)
			y_hat_val = self.predict(x_val, B)
			y_hat_test = self.predict(x_test, B)
			### Ridge Regression
			# ridge_model = Ridge(alpha=alpha)
			# ridge_model.fit(x_train, y_train)
			# y_hat_train = ridge_model.predict(x_train)
			# y_hat_val = ridge_model.predict(x_val)
			# y_hat_test = ridge_model.predict(x_test)


			#Normalized correlation coefficient
			r2t += self.cc_norm(y_hat_train, y_train, sp=sp)
			r2v += self.cc_norm(y_hat_val, y_val, sp=sp)
			r2tt += self.cc_norm(y_hat_test, y_test, sp=sp)
			
		r2t /= 5
		r2v /= 5
		r2tt /= 5
	
		return r2t, r2v,r2tt

	def compute_cc_norm(self, x, y, sp=1):
		# provide 'sp' for normalized correlation coefficient...!
		r2t = np.zeros(1)
		r2v = np.zeros(1)
		r2tt = np.zeros(1)
		
		m = int(x.shape[0])
		n2 = int(m*0.9)
		x_test = x[n2:, :]
		y_test = y[n2:]    
		
		# signal power, will be used for normalization
		#sp = self.dataset.signal_power(win, channel)
		for i in range(5):
			a = int(i*0.2*n2)
			b = int((i+1)*0.2*n2)
			
			x_val = x[a:b, :] 
			y_val = y[a:b] 
			
			x_train = np.concatenate((x[:a,:], x[b:n2,:]), axis=0)
			y_train = np.concatenate((y[:a], y[b:n2]))
			
			# Linear Regression...!
			B = self.regression_param(x_train, y_train)
			y_hat_train = self.predict(x_train, B)
			y_hat_val = self.predict(x_val, B)
			y_hat_test = self.predict(x_test, B)
			
			#Normalized correlation coefficient
			r2t += self.cc_norm(y_hat_train, y_train, sp)
			r2v += self.cc_norm(y_hat_val, y_val, sp)
			r2tt += self.cc_norm(y_hat_test, y_test, sp)
			
		r2t /= 5
		r2v /= 5
		r2tt /= 5
	
		return r2t, r2v,r2tt    
				
	

	def cc_norm(self, y_hat, y, sp):
		# 'sp==1' means, signal power not provided, then return simple correlation coefficient i.e. 'un-normalized'
		if sp==1:
			factor = np.var(y)
		else:
			factor = sp

		return np.cov(y_hat, y)[0,1]/(np.sqrt(np.var(y_hat)*factor))

	def regression_param(self, X, y):
		B = linalg.lstsq(X, y)[0]
		return B

	def predict(self, X, B):
		return X@B


	def FE_r2_channel(self, layer, win, channel):
		k = int(win/40)    # 40 is the min, bin size for 'Speech2Text' transformer model 
		print(f"k = {k}")
		r2t = np.zeros(1)
		r2v = np.zeros(1)
		pct = np.zeros(1)
		pcv = np.zeros(1)
		#downsamples if k>1 
		if k >1:
			feats = self.down_sample_features(self.demean_features[layer], k)
		else:
			feats = self.demean_features[layer]

		m = int(feats.shape[0] *0.75)
		x_train = feats[0:m, :]
		x_test = feats[m:, :]
		
		# for i in range(self.dataset.num_channels):
		y = self.demean_spikes(ch=channel)
		if k>1:
			y = self.down_sample_spikes(y,k)
		y_train = y[0:m]
		y_test = y[m:]
		B = self.regression_param(x_train, y_train)

		r2t = self.regression_score(x_train, y_train, B)
		r2v = self.regression_score(x_test, y_test, B)
		pct = (np.corrcoef(self.predict(x_train, B), y_train)[0,1])**2
		pcv = (np.corrcoef(self.predict(x_test, B), y_test)[0,1])**2
		return r2t, r2v, pct, pcv

	#   def signal_power(self, win, ch):
	#     sents = [12,13,32,43,56,163,212,218,287,308]
	#     sp = 0
	#     for s in sents:
	#         r = self.dataset.retrieve_spike_counts_for_all_trials(sent=s, w=win)[ch]
	#         N = r.shape[0]
	#         s = np.sum(r, axis=0)
	#         n1 = np.var(s, axis=0)
	#         n2 = 0
	#         for i in range(r.shape[0]):
	#             n2 += np.var(r[i])
	#         sp += (n1 - n2)/(N*(N-1))
	#     sp /= len(sents)
	#     return sp 


	def r2(self, labels, predictions):
		score = 0.0
		mean = np.mean(labels)
		denom = np.sum(np.square(labels - mean))
		num = np.sum(np.square(labels - predictions))
		score = 1 - num/denom
		return score
	def regression_score(self, X,y, B):
		y_hat = self.predict(X,B)
		return self.r2(y, y_hat)

	## for L2 regularisation
	def get_layer_values_and_spikes(self, layer, win, sent_list=[12]):
		# features, _ = self.get_transformer_features(sent_list)

		if layer<2:
			d=1
		else:
			d=0

		features = torch.cat([self.all_features[layer][i] for i in sent_list], dim=d).detach().numpy()

		if self.model_name=='transformer':
			#def_w = 20
			# offset is used to match different rounding error in 1st conv layer vs the rest of the layers...!
			n = self.spikes_dict[1]

			if layer <1:
				feats = features.transpose()
				# offset = -0.25
				def_w = 20 
				n = self.spikes_dict[0]
			elif layer < 2:
				feats = features.transpose()
				def_w = 40
				# offset = 0.39
			else:
				feats = features
				def_w = 40
				# offset = 0.39
		else:
			def_w = 25
			
		k = int(win/def_w)    # 40 is the min, bin size for 'Speech2Text' transformer model 
		# print(f"k = {k}")
		spikes = list(map(lambda i: np.array(list(n[i].values())).T, sent_list))


		if k >1:
			feats = self.down_sample_features(feats, k)
			spikes = self.down_sample_spikes(np.concatenate(spikes, axis=0), k)
		
		# n = self.simply_spikes(ch=channel, delay=delay, w=def_w, offset=offset, sent_list=sent_list)

		return feats, spikes

	# def get_all_channels(self, def_w, offset=0, delay=0, k_val=1, sent_list=[12]):
	# 	n_all_channel = []
	# 	for channel in range(1):
	# 		n = self.simply_spikes(ch=channel, delay=delay, w=def_w, offset=offset, sent_list=sent_list)
	# 		if k_val>1:
	# 			n = self.down_sample_spikes(n, k_val)
	# 		n_all_channel.append(n)
	# 	return np.array(n_all_channel).T

#   def get_pcs(self, layer, sents):
#       #layer = 0
#       #sents = [495, 496, 497]
#       feats = [{} for _ in sents]
#       feats_pcs = {}
#       for i, s in enumerate(sents):
#         feats[i], _ = self.get_transformer_features(s, s+1)
#       layer_features = self.features[layer]
#       m = layer_features.shape[0]
#       pc = PCA(n_components=2)
#       pc.fit(layer_features[:int(0.75*m),:])
#       for i, s in enumerate(sents):
#         feats_pcs[i] = pc.transform(feats[i][layer]) 
#       return feats_pcs

#   def plot_pcs(self, l=0, sents=[495,496,497]):
#       c_maps = ['Greys', 'Purples', 'Blues', 'Oranges',
#                 'Greens', 'Reds',
#                 #'YlOrBr', 'YlOrRd', 'OrRd', 'PuRd', 'RdPu', 'BuPu',
#                 #'GnBu', 'PuBu', 'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn'
#                 ] 
#       leg_colors = ['tab:gray','tab:purple','tab:blue','tab:orange',
#                     'tab:green','tab:red']

#       pcs = self.get_pcs(layer=l, sents=sents)

#       for i in range(len(pcs.keys())):
#         shades = np.arange(0,pcs[i].shape[0])

#         plt.scatter(pcs[i][:,0], pcs[i][:,1], label=f"sent: {sents[i]}", cmap=c_maps[(i+2)%len(c_maps)], c=shades, vmin=-40, vmax=80)

#       leg = plt.legend(loc='best')
#       for i in range(len(pcs.keys())):
#         leg.legendHandles[i].set_color(leg_colors[(i+2)%len(leg_colors)])

#       plt.xlabel(f"PC1")
#       plt.ylabel(f"PC2")
#       plt.title(f"{self.layers[l]}")


