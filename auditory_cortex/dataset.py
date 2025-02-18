from scipy import io
import numpy as np
import json
import os
import matplotlib.pyplot as plt

import auditory_cortex.utils as utils

class NeuralData:
  """Neural_dataset class loads neural data, from the directory specified at creation & 
  provides functions to retrieve 'relative/absolute' spike times, or spike counts in the durations
  whose width is specified by 'win'
  'dir': (String) Path to the directory containing data files and the json_file.
  'json_file': (String) Default: 'Neural_data_files.json' specifies data files to be loaded.
  """
  def __init__(self, dir, sub,  mat_file = 'out_sentence_details_timit_all_loudness.mat', verbose=False):
    print(f"Loading Neural data for session: {sub} ... ", end='')
    self.sub = sub
    self.dir = dir
    self.sentences = io.loadmat(os.path.join(self.dir, mat_file), struct_as_record = False, squeeze_me = True, )
    self.features = self.sentences['features']
    self.phn_names = self.sentences['phnnames']
    self.sentdet = self.sentences['sentdet']
    self.fs = self.sentdet[0].soundf   #since fs is the same for all sentences, using fs for the first sentence
    self.names = os.listdir(os.path.join(self.dir, self.sub)) 
    # print(self.names)
    self.spikes, self.trials = self.load_data(verbose=verbose)
    self.num_channels = len(self.spikes.keys())
    self.sents = np.arange(1,500)
    self.sent_sections = {}

    print("Done.")
    # print(f"Data from {self.num_channels} channels loaded...!")

  def load_data(self, verbose):
    """ Loads data from __MUspk.mat files and returns a tuple of dictionaries. 
    Takes in the path of directory having the __MUspk.mat files and json file 
    with filenames to load. 
    'dir: (string) address of location with __MUspk.mat files
    'j_file': (string) json file with names of __Muspk.mat files to load
    Returns:
    (spikes, trials): 1st carries dictionary of spike structs read from __MUspk files
    and second one carries dictionary of trial structs.
    """
    path = os.path.join(self.dir, self.sub)
    spikes = {}
    trials = {}
    data = {}
    self.names.sort()
    for i, name in enumerate(self.names):
      if verbose:
        print(name)
      if 'MUspk' in name:
        # print(name)
        data[i] = io.loadmat(os.path.join(path,name), squeeze_me = True, struct_as_record = False)
        spikes[i] = data[i]['spike']
        trials[i] = data[i]['trial']
    
    return spikes, trials

  def phoneme(self, sent=1):
    # subtracting 1 because timitStimcodes range [1,500) and sent indices range [0,499)
    sent -= 1
     
    #indices where phoneme exists
    phoneme_present = np.amax(self.sentdet[sent].phnmat, axis=0)
    # one-hot-encoding to indices (these may carry 0 where no phoneme is present)
    indices = np.argmax(self.sentdet[sent].phnmat, axis = 0)
    #eliminate 0's for no phonemes
    indices = indices[np.where(phoneme_present>0)]
    return self.phn_names[indices]
  
  def audio(self, sent=1):
    # subtracting 1 because timitStimcodes range [1,500) and sent indices range [0,499)
    sent -= 1
    fs = self.sentdet[sent].soundf
    bef, aft = 0.5, 0.5
    #bef = self.sentdet[sent].befaft[0]
    #aft = self.sentdet[sent].befaft[1]
    sound = self.sentdet[sent].sound
    sound = sound[int(bef*fs):-int(aft*fs)]
    
    return sound

  def duration(self, sent=1):
    # subtracting 1 because sent_id =1 is stored at index 0 in sentdet and so on...
    sent -= 1
    bef, aft = 0.5, 0.5
    #bef = self.sentdet[sent].befaft[0]
    #aft = self.sentdet[sent].befaft[1]
    duration = self.sentdet[sent].duration - (bef + aft)
    return duration

  def audio_phoneme_data(self):
    audio = {}
    phnm = {}
    for i in range(499):
      phnm[i] = self.phoneme(i)
      audio[i] = self.audio(i)
    return audio, phnm
  
  def get_trials(self, sent):
    #get all trials for sentence 'sent'
    #Trials are repeated for these sentences only
    #sents = [12,13,32,43,56,163,212,218,287,308]

    #trials = np.unique(obj.dataset.spikes[1].trial[obj.dataset.spikes[1].timitStimcode==sent])
    # Using channel 0 trials dict to get list of trials for 'sent', but trials for all the channels are the same 
    #only the outcome 'spikes' can vary, so that is the reason of not using spikes
    
    try: 
      trials = (np.where(self.trials[0].timitStimcode == sent)[0]) + 1          # adding 1 to match the indexes
      return trials
    except:
      print("No trial data found...!")
    

  def retrieve_spike_counts_for_all_trials(self, sent, win=50, delay=0):
    
    trials = self.get_trials(sent)
    spk = self.retrieve_spike_counts(trial=trials[0], win = win, delay=delay)
    spikes = {i:np.zeros((len(trials), spk[0].shape[0])) for i in range(self.num_channels)}
    for i in range(self.num_channels):
        spikes[i][0] = spk[i]
    for x, tr in enumerate(trials[1:]):
        spikes_tr = self.retrieve_spike_counts(trial=tr, win = win, delay=delay)
        for i in range(self.num_channels):
            spikes[i][x+1] = spikes_tr[i]
    return spikes

  def retrieve_spike_times(self, sent=212, trial = 0 , timing_type = 'relative'):
    """Returns times of spikes, relative to stimulus onset or absolute time
    'sent' (int) index of stimulus sentencce 
    'trial' (int) specific trial # for the above sentence, some sentences may have 
    neural spikes for more than 1 trials of the given sentence. By default result of 
    foremost trial will be returned.
    'timing_type' (string:) 'relative' (default) returns spike times relative to StimOnset time, 
                    'absolute' returns spike times in seconds.
    
    """
    s_times = {}
    if trial ==0:
      # if no trial # is provided, use the first trial for the given sentence
      # tr carries the trial # to index through spike data
      #tr = self.spikes[1].trial[self.spikes[1].timitStimcode==sent][trial] 
      # Extracting 'trial #' using the first channel...!
      # tr = (np.where(self.trials[0].timitStimcode == sent)[0][0]) + 1      # adding 1 to match the indexes
      tr = self.get_trials(sent)[0]           # Using 1st trial for stimuli with multiple trials
    else:
      #print('Please provide Trial # corresponding to the provided sentence using of spike.trial')
      tr = trial
    # ADDED one to i to make it match indices
    for i in range(self.num_channels):
      #spike_indices to index through spike fields
      # print("here: ",i, tr)
      # j = i+1
      j = i
      spike_indices = np.where(self.spikes[j].trial == tr)
      #spike times relative to the stimuls On time (Stimon)
      if timing_type == 'relative':
        s_times[i] = self.spikes[j].stimlock[spike_indices]   
      elif timing_type == 'absolute':
        s_times[i] = self.spikes[j].spktimes[spike_indices]   
    
    return s_times

  def create_bins(self, s_times, sent=212, trial=0, win=50, delay = 0):
    """Returns bins containing number of spikes in the 'win' durations
    following the stimulus onset.
      
    Args:
        sent (int): ID of the audio stimulus (sentence)
        trial (int): trial ID to create bins for. Can be used to get binned spikes
            directly using the trial number, instead of sent ID.
        win (int): miliseconds specifing the width of time slots for bins.
        delay (ms): Delaying the features versus spikes. (we can also think of this
            as advancing the spikes, that would mean delaying the spikes w.r.t. to spikes.)

    """
    if trial != 0:
        trial -= 1
        sent = self.trials[0].timitStimcode[trial]
    win = win/1000
    delay = delay/1000
    bins = {}             #miliseconds
	# round the 3rd decimal digit, before ceiling...!
    n = int(np.ceil(round(self.duration(sent)/win, 3)))
    
    # store boundaries of sent thirds...
    one_third = int(n/3)
    two_third = int(2*n/3)
    self.sent_sections[sent] = [0, one_third, two_third, n] 


    for i in range(self.num_channels):
      tmp = np.zeros(n, dtype=np.int32) 
      j = 0
      st = delay
      en = st+win                  #End time for ongoing search window
      for val in s_times[i]:
        if val < (tmp.size * win + delay):
          if (val<= en and val>st):
            tmp[j] += 1
            
          elif val>en:    
            while(val > en):
              j += 1
              st += win
              en += win
            if j<n:
              tmp[j] += 1
            
      bins[i] = tmp
    
    return bins

  def retrieve_spike_counts(self, sent=212, trial = 0, win = 50, delay=0):
    """Returns number of spikes in every 'win' miliseconds duration following the 
    stimulus onset time.
    'sent' (int) index of stimulus sentencce 
    'trial' (int) specific trial # for the above sentence, some sentences may have 
    neural spikes for more than 1 trials of the given sentence. By default result of 
    foremost trial will be returned.
    'win' (int: 50) miliseconds specifying the time duration of each bin
    """
    #get 'relative' spike times for the given sentence and trial
    s_times = self.retrieve_spike_times(sent=sent, trial=trial)
    #return spikes count in each bin
    output = self.create_bins(s_times, sent=sent, trial=trial, win = win,delay=delay)
    
    return output

  def spike_counts(self, sent=212, trial=0, win=50, delay=0):
    ## Spike count using np.histogram function, this is in addition to
    #  my own binning implementation in Retrieve_spikes_count()
    # and they both give the same output
    s_times = self.retrieve_spike_times(sent=sent, trial=trial)
    win = win/1000
    counts = {}
   
    duration = round(self.duration(sent),3)  #round off to 3 decimals...
    bins = np.arange(delay, delay + duration, win)
    for i in range(self.num_channels):
        counts[i], _ = np.histogram(s_times[i], bins)
    return counts

  def extract_spikes(self, bin_width=20, delay=0, sents = None):
    """Return neural spikes for given sents"""
    if sents is None:
        sents = self.sents
    raw_spikes = {}
    for x,i in enumerate(sents):
        spikes = self.retrieve_spike_counts(sent=i,win=bin_width,delay=delay)
        raw_spikes[i] = np.stack([spikes[ch] for ch in range(self.num_channels)], axis=1)
    self.raw_spikes =  raw_spikes

  def unroll_spikes(self, sents=None, features_delay_trim=None, third=None):
    """
    Unroll and concatenate time axis of extracted spikes.

    Args:
        sents (List): indices of sents.
        third (int) [1,2,3]: Default=None, section of sents to be retrieved.

    Returns:
        
    """
    if sents is None:
      sents = self.raw_spikes.keys()

    if features_delay_trim is None:
       trim = 0
    else:
       trim = features_delay_trim
    if third is None:
      spikes = np.concatenate([self.raw_spikes[sent][trim:] for sent in sents], axis=0)
    else:
       spikes = np.concatenate([self.raw_spikes[sent][self.sent_sections[sent][third-1]:self.sent_sections[sent][third]] for sent in sents], axis=0)
    return spikes

  def load_spikes(self, bin_width=20, delay=0, sents=None):
    if sents is None:
        sents = self.sents
    self.extract_spikes(
       bin_width=bin_width, delay=delay, sents=sents
    )
    return self.unroll_spikes()

  def get_repeated_trials(self, sents=None, bin_width=20, delay=0):
      """Get repeated trials for given sents as 'ndarray'. """
      if sents is None:
          sents = [12,13,32,43,56,163,212,218,287,308]
      spikes_dict = {}
      min_repeats = 500   #repetition of trials (mostly it is 11)
      for s in sents:
          spikes_sentence = self.retrieve_spike_counts_for_all_trials(sent=s, win = bin_width, delay=delay)
          spikes_dict[s] = np.stack([spikes_sentence[ch] for ch in range(self.num_channels)], axis=-1)
          if spikes_dict[s].shape[0] < min_repeats:
              min_repeats = spikes_dict[s].shape[0] 
      all_repeated_trials = np.concatenate([spikes_dict[s][:min_repeats,:,:] for s in sents], axis=1)
      return all_repeated_trials

  def get_normalizer(self, sents=None, bin_width=20, delay=0, n=1000):
      """Compute dist. of normalizer and return median."""
      if sents is None:
          sents = [12,13,32,43,56,163,212,218,287,308]
      all_repeated_trials = self.get_repeated_trials(sents=sents, bin_width=bin_width, delay=delay)
      normalizer_all = utils.inter_trial_corr(all_repeated_trials, n=n)
      normalizer_all_med = np.median(normalizer_all, axis=0)
      return normalizer_all_med




    
    # Neural Data Plotting Functions....
    
  def rastor_plot(self ,sent=12, ch=9):
    # Rastor plot for all the trials of given 'sent' and channel 'ch'

    #Repeated trials for following timitStimcodes only
    #sents = [12,13,32,43,56,163,212,218,287,308]
    spikes = {}
    max_time = 0
    #fig = plt.figure(figsize=(12,6))
    trials = self.get_trials(sent=sent)
    for i, tr in enumerate(trials):
        spikes[i] = self.retrieve_spike_times(sent=sent, trial=tr)[ch]
        mx = np.amax(spikes[i], axis=0)
        if mx > max_time:
            max_time = mx 
        #print(spikes[i].shape)
        plt.eventplot(spikes[i], lineoffsets=i+1, linelengths=0.3, linestyles='-', linewidths=8)
    plt.xlim(0,self.duration(sent))
    plt.xlabel('Time (s)', fontsize=14)
    plt.ylabel('Trials', fontsize=14)
    #plt.title(f"Rastor Plot for session: {self.sub}, sentence: {sent}, ch: '{self.names[ch]}'", fontsize=14, fontweight='bold')
    
  def psth(self, sent=12, ch=9, win = 40):
    trials = self.get_trials(sent=sent)
    spikes = {}
    #fig = plt.figure(figsize=(12,6))
    for i, tr in enumerate(trials):
        spikes[i] = self.retrieve_spike_counts(sent=12, trial=tr, win=win)[ch]
        if i==0:
            psth = np.zeros(spikes[i].shape[0])
        psth += spikes[i]
        #print(spikes[i].shape)
    #print(psth.shape)
 
    psth /= trials.size
    edges = np.float64(np.arange(0, psth.shape[0]))*win/1000

    return edges, psth
    # plt.bar(edges,psth, width=(0.8*win/1000))
    # plt.xlim(0,self.duration(sent))
    # #plt.xlabel('Time (s)', fontsize=14)
    # plt.ylabel('Spike Counts', fontsize=14)
    #plt.title(f"PSTH session: {self.sub}, sentence: {sent}, ch: '{self.names[ch]}', bin: {win}", fontsize=14, fontweight='bold')

    
  def signal_power(self, win, ch, sents = [12,13,32,43,56,163,212,218,287,308]):
    
    sp = 0
    for s in sents:
        r = self.retrieve_spike_counts_for_all_trials(sent=s, w=win)[ch]
        N = r.shape[0]
        trail_sum = np.sum(r, axis=0)
        n1 = np.var(trail_sum, axis=0)
        n2 = 0
        for i in range(r.shape[0]):
            n2 += np.var(r[i])
        sp += (n1 - n2)/(N*(N-1))
    sp /= len(sents)
    return sp