import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import jsPDF from 'jspdf';
import 'jspdf-autotable';

const API_URL = 'http://localhost:8000';

function SpeechRecognition({ user, onBack }) {
  const [activeTab, setActiveTab] = useState('record');
  const [selectedLanguage, setSelectedLanguage] = useState(null);
  const [languageSelected, setLanguageSelected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [fullText, setFullText] = useState('');
  const [interimText, setInterimText] = useState('');
  const [seconds, setSeconds] = useState(0);
  const [wordCount, setWordCount] = useState(0);
  const [charCount, setCharCount] = useState(0);
  const [audioChunks, setAudioChunks] = useState([]);
  const [audioUrl, setAudioUrl] = useState(null);
  const [saved, setSaved] = useState(false);
  const [saveResult, setSaveResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [summary, setSummary] = useState('');
  const [summaryType, setSummaryType] = useState('');
  const [summaryCompression, setSummaryCompression] = useState(0);
  const [summaryOriginalWords, setSummaryOriginalWords] = useState(0);
  const [summarySummaryWords, setSummarySummaryWords] = useState(0);
  const [keyPoints, setKeyPoints] = useState([]);
  const [generatingSummary, setGeneratingSummary] = useState(false);
  const [records, setRecords] = useState([]);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [error, setError] = useState('');
  const [transcriptionStats, setTranscriptionStats] = useState({
    sentences: 0,
    paragraphs: 0,
    estimatedReadingTime: 0
  });
  const [showHelper, setShowHelper] = useState(true);
  const [transcribing, setTranscribing] = useState(false);
  
  // Refs for stable text handling
  const timerRef = useRef(null);
  const recognitionRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const fullTextRef = useRef('');
  const interimTextRef = useRef('');
  const isFinalizingRef = useRef(false);
  const isRecognitionActiveRef = useRef(false);

  // Helper steps for new users
  const helperSteps = [
    { icon: '🌍', title: 'Select Language', description: 'Choose English or Kinyarwanda' },
    { icon: '🎙️', title: 'Start Recording', description: 'Speak clearly into your microphone' },
    { icon: '📝', title: 'Get Transcription', description: 'AI generates text in real-time' },
    { icon: '💾', title: 'Save & Export', description: 'Save to library or export as PDF' }
  ];

  const getAuthToken = () => localStorage.getItem('token');
  
  const api = axios.create({
    baseURL: API_URL,
  });

  api.interceptors.request.use((config) => {
    const token = getAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  useEffect(() => {
    fetchRecords();
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {}
      }
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, []);

  // Auto-hide helper after user interacts
  useEffect(() => {
    if (languageSelected || fullText || isRecording) {
      setShowHelper(false);
    }
  }, [languageSelected, fullText, isRecording]);

  const fetchRecords = async () => {
    try {
      const response = await api.get('/api/speech/records');
      setRecords(response.data.records);
    } catch (err) {
      console.error('Error fetching records:', err);
    }
  };

  // Format text into sentences and paragraphs based on length
  const formatTextIntoParagraphs = (text) => {
    if (!text) return text;
    
    let sentences = [];
    let currentSentence = '';
    
    for (let i = 0; i < text.length; i++) {
      currentSentence += text[i];
      if (text[i].match(/[.!?]/) && (i + 1 === text.length || text[i + 1] === ' ')) {
        sentences.push(currentSentence.trim());
        currentSentence = '';
      }
    }
    if (currentSentence.trim()) {
      sentences.push(currentSentence.trim());
    }
    
    const wordsPerParagraph = 80;
    const paragraphs = [];
    let currentParagraph = [];
    let currentWordCount = 0;
    
    for (const sentence of sentences) {
      const sentenceWords = sentence.split(/\s+/).length;
      
      if (currentWordCount + sentenceWords > wordsPerParagraph && currentParagraph.length > 0) {
        paragraphs.push(currentParagraph.join(' '));
        currentParagraph = [sentence];
        currentWordCount = sentenceWords;
      } else {
        currentParagraph.push(sentence);
        currentWordCount += sentenceWords;
      }
    }
    
    if (currentParagraph.length > 0) {
      paragraphs.push(currentParagraph.join(' '));
    }
    
    return paragraphs.join('\n\n');
  };

  const updateTextStats = (text) => {
    const words = text.trim() ? text.trim().split(/\s+/).filter(w => w).length : 0;
    const chars = text.length;
    const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 0).length;
    const readingTime = Math.ceil(words / 200);
    
    setWordCount(words);
    setCharCount(chars);
    setTranscriptionStats({
      sentences: Math.max(0, sentences),
      paragraphs: Math.max(0, Math.ceil(sentences / 3)),
      estimatedReadingTime: readingTime
    });
  };

  const handleLanguageSelect = (lang) => {
    setSelectedLanguage(lang);
    setLanguageSelected(true);
    setError('');
    setShowHelper(false);
    if (isRecording) {
      stopRecording();
    }
    clearText();
  };

  const generateSmartSummary = (text) => {
    if (!text || text.length < 20) {
      return { 
        summary: text || '', 
        type: 'No Summary', 
        compression: 0, 
        originalWords: 0, 
        summaryWords: 0 
      };
    }
    
    let sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 10);
    
    if (sentences.length === 0) {
      return {
        summary: text.substring(0, 200) + (text.length > 200 ? '...' : ''),
        type: 'Short Summary',
        compression: Math.round((200 / text.length) * 100),
        originalWords: text.split(/\s+/).length,
        summaryWords: 30
      };
    }
    
    const totalWords = text.split(/\s+/).length;
    const totalSentences = sentences.length;
    
    let targetPercent, summaryType;
    
    if (totalWords < 50) {
      targetPercent = 0.7;
      summaryType = '📖 Full Summary';
    } else if (totalWords < 150) {
      targetPercent = 0.5;
      summaryType = '📘 Standard Summary';
    } else if (totalWords < 400) {
      targetPercent = 0.35;
      summaryType = '📙 Concise Summary';
    } else {
      targetPercent = 0.25;
      summaryType = '📊 Executive Summary';
    }
    
    const targetWordCount = Math.max(30, Math.floor(totalWords * targetPercent));
    
    const scoredSentences = sentences.map((sentence, idx) => {
      let score = 0;
      const sentenceWords = sentence.split(/\s+/).length;
      
      if (idx === 0) score += 5;
      if (idx === sentences.length - 1) score += 4;
      if (idx === 1) score += 2;
      if (idx === 2) score += 1;
      
      if (sentenceWords >= 8 && sentenceWords <= 25) score += 2;
      else if (sentenceWords > 35) score -= 1;
      
      const importantKeywords = [
        'important', 'significant', 'key', 'essential', 'main', 'conclusion',
        'therefore', 'thus', 'result', 'finally', 'akamaro', 'ingenzi',
        'nyamukuru', 'ibanze', 'yesu', 'imana', 'ndagukunda', 'urakoze',
        'ngirakamaro', 'mugisha', 'amahoro', 'ubumwe', 'iterambere'
      ];
      for (const kw of importantKeywords) {
        if (sentence.toLowerCase().includes(kw)) {
          score += 1.5;
          break;
        }
      }
      
      return { sentence, score, words: sentenceWords, index: idx };
    });
    
    scoredSentences.sort((a, b) => b.score - a.score);
    
    let selected = [];
    let currentWordCount = 0;
    const selectedIndices = new Set();
    
    const firstSentence = scoredSentences.find(s => s.index === 0);
    if (firstSentence) {
      selected.push(firstSentence);
      currentWordCount += firstSentence.words;
      selectedIndices.add(0);
    }
    
    const lastSentence = scoredSentences.find(s => s.index === sentences.length - 1);
    if (lastSentence && !selectedIndices.has(lastSentence.index)) {
      if (currentWordCount + lastSentence.words <= targetWordCount * 1.3) {
        selected.push(lastSentence);
        currentWordCount += lastSentence.words;
        selectedIndices.add(lastSentence.index);
      }
    }
    
    for (const s of scoredSentences) {
      if (!selectedIndices.has(s.index) && currentWordCount + s.words <= targetWordCount * 1.2) {
        selected.push(s);
        currentWordCount += s.words;
        selectedIndices.add(s.index);
      }
      if (currentWordCount >= targetWordCount) break;
    }
    
    selected.sort((a, b) => a.index - b.index);
    
    let summary = selected.map(s => s.sentence).join('. ') + '.';
    if (summary.length > 0) {
      summary = summary.charAt(0).toUpperCase() + summary.slice(1);
    }
    summary = summary.replace(/\s+/g, ' ').trim();
    
    const summaryWords = summary.split(/\s+/).length;
    const compression = totalWords > 0 ? Math.round((summaryWords / totalWords) * 100) : 0;
    
    return {
      summary,
      type: summaryType,
      compression,
      originalWords: totalWords,
      summaryWords,
      totalSentences
    };
  };

  const extractKeyPoints = (text) => {
    if (!text) return [];
    
    let sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 15);
    
    if (sentences.length === 0) {
      return [{
        number: 1,
        text: text.substring(0, 150) + (text.length > 150 ? '...' : ''),
        importance: 'medium',
        icon: '🟡',
        score: 0
      }];
    }
    
    const scored = sentences.map((sentence, idx) => {
      let score = 0;
      const wordLen = sentence.split(/\s+/).length;
      
      if (idx === 0) score += 3;
      if (idx === sentences.length - 1) score += 2.5;
      if (idx === 1) score += 1.5;
      if (idx === 2) score += 1;
      
      if (wordLen >= 10 && wordLen <= 25) score += 1.5;
      else if (wordLen > 45) score -= 0.5;
      
      const keywords = [
        'important', 'significant', 'key', 'essential', 'main', 'conclusion',
        'therefore', 'thus', 'result', 'finally', 'akamaro', 'ingenzi',
        'nyamukuru', 'yesu', 'imana', 'ndagukunda', 'urakoze', 'ngirakamaro',
        'mugisha', 'amahoro', 'ubumwe', 'iterambere', 'recommend', 'suggest'
      ];
      for (const kw of keywords) {
        if (sentence.toLowerCase().includes(kw)) {
          score += 1.2;
          break;
        }
      }
      
      return { sentence: sentence.trim(), score, originalIndex: idx };
    });
    
    scored.sort((a, b) => b.score - a.score);
    const numPoints = Math.min(5, Math.max(3, Math.floor(sentences.length * 0.25)));
    const topPoints = scored.slice(0, numPoints);
    topPoints.sort((a, b) => a.originalIndex - b.originalIndex);
    
    return topPoints.map((point, i) => ({
      number: i + 1,
      text: point.sentence,
      importance: point.score >= 3 ? 'high' : (point.score >= 1.8 ? 'medium' : 'low'),
      icon: point.score >= 3 ? '🔴' : (point.score >= 1.8 ? '🟡' : '🟢'),
      score: point.score
    }));
  };

  const generateSummaryAndKeyPoints = async () => {
    if (!fullText.trim()) {
      setError('No text to summarize. Please record something first.');
      setTimeout(() => setError(''), 3000);
      return;
    }

    setGeneratingSummary(true);
    setError('');

    try {
      const response = await api.post('/api/text/analyze', {
        text: fullText,
        language: selectedLanguage || 'en',
        duration_seconds: seconds,
      });

      if (response.data.success) {
        setFullText(response.data.formatted_text || fullText);
        setSummary(response.data.summary);
        setSummaryType(response.data.summary_metrics?.type || '');
        setSummaryCompression(parseInt(response.data.summary_metrics?.compression) || 0);
        setSummaryOriginalWords(response.data.summary_metrics?.original_words || 0);
        setSummarySummaryWords(response.data.summary_metrics?.summary_words || 0);
        setKeyPoints(response.data.key_points || []);
      } else {
        setError('Could not generate a summary right now.');
        setTimeout(() => setError(''), 3000);
      }
    } catch (err) {
      console.error('Analyze error:', err);
      // Fall back to the client-side extractive summary rather than leaving
      // the user with nothing if the backend call fails.
      const summaryResult = generateSmartSummary(fullText);
      setSummary(summaryResult.summary);
      setSummaryType(summaryResult.type);
      setSummaryCompression(summaryResult.compression);
      setSummaryOriginalWords(summaryResult.originalWords);
      setSummarySummaryWords(summaryResult.summaryWords);
      setKeyPoints(extractKeyPoints(fullText));
    } finally {
      setGeneratingSummary(false);
    }
  };

  const exportAsPDF = () => {
    if (!fullText && !summary && keyPoints.length === 0) {
      setError('No content to export');
      setTimeout(() => setError(''), 3000);
      return;
    }

    try {
      const doc = new jsPDF();
      let yPos = 20;
      
      doc.setFontSize(22);
      doc.setTextColor(24, 119, 242);
      doc.text('Speech Transcription Report', 105, yPos, { align: 'center' });
      yPos += 15;
      
      doc.setFontSize(10);
      doc.setTextColor(100, 100, 100);
      doc.text(`Date: ${new Date().toLocaleString()}`, 20, yPos);
      yPos += 7;
      doc.text(`Language: ${selectedLanguage === 'rw' ? 'Kinyarwanda' : 'English'}`, 20, yPos);
      yPos += 7;
      doc.text(`Duration: ${Math.floor(seconds / 60)}:${(seconds % 60).toString().padStart(2, '0')}`, 20, yPos);
      yPos += 7;
      doc.text(`Words: ${wordCount}`, 20, yPos);
      yPos += 7;
      doc.text(`Characters: ${charCount}`, 20, yPos);
      yPos += 7;
      doc.text(`Sentences: ${transcriptionStats.sentences}`, 20, yPos);
      yPos += 15;
      
      doc.setFontSize(14);
      doc.setTextColor(0, 0, 0);
      doc.text('📝 Full Transcription', 20, yPos);
      yPos += 10;
      
      doc.setFontSize(10);
      const splitText = doc.splitTextToSize(fullText || 'No transcription available', 170);
      for (let i = 0; i < splitText.length; i++) {
        if (yPos > 270) {
          doc.addPage();
          yPos = 20;
        }
        doc.text(splitText[i], 20, yPos);
        yPos += 6;
      }
      yPos += 10;
      
      if (summary) {
        if (yPos > 250) {
          doc.addPage();
          yPos = 20;
        }
        doc.setFontSize(14);
        doc.setTextColor(0, 0, 0);
        doc.text('📋 AI Summary', 20, yPos);
        yPos += 10;
        
        doc.setFontSize(9);
        doc.setTextColor(100, 100, 100);
        doc.text(`Type: ${summaryType} | Compression: ${summaryCompression}%`, 20, yPos);
        yPos += 6;
        doc.text(`Original: ${summaryOriginalWords || wordCount} words | Summary: ${summarySummaryWords || summary.split(/\s+/).length} words`, 20, yPos);
        yPos += 10;
        
        doc.setFontSize(10);
        doc.setTextColor(0, 0, 0);
        const summarySplit = doc.splitTextToSize(summary, 170);
        for (let i = 0; i < summarySplit.length; i++) {
          if (yPos > 270) {
            doc.addPage();
            yPos = 20;
          }
          doc.text(summarySplit[i], 20, yPos);
          yPos += 6;
        }
        yPos += 10;
      }
      
      if (keyPoints.length > 0) {
        if (yPos > 250) {
          doc.addPage();
          yPos = 20;
        }
        doc.setFontSize(14);
        doc.setTextColor(0, 0, 0);
        doc.text('🔑 Key Points', 20, yPos);
        yPos += 10;
        
        doc.setFontSize(10);
        for (const point of keyPoints) {
          if (yPos > 270) {
            doc.addPage();
            yPos = 20;
          }
          const priorityColor = point.importance === 'high' ? [220, 38, 38] : (point.importance === 'medium' ? [245, 158, 11] : [16, 185, 129]);
          doc.setTextColor(priorityColor[0], priorityColor[1], priorityColor[2]);
          doc.text(`${point.number}. ${point.importance.toUpperCase()} PRIORITY`, 20, yPos);
          yPos += 7;
          doc.setTextColor(0, 0, 0);
          const pointText = doc.splitTextToSize(point.text, 160);
          for (let i = 0; i < pointText.length; i++) {
            if (yPos > 270) {
              doc.addPage();
              yPos = 20;
            }
            doc.text(pointText[i], 25, yPos);
            yPos += 5;
          }
          yPos += 5;
        }
      }
      
      const pageCount = doc.internal.getNumberOfPages();
      for (let i = 1; i <= pageCount; i++) {
        doc.setPage(i);
        doc.setFontSize(8);
        doc.setTextColor(150, 150, 150);
        doc.text(`Generated by AudioText Pro - ${new Date().toLocaleDateString()} - Page ${i} of ${pageCount}`, 105, 290, { align: 'center' });
      }
      
      doc.save(`speech_transcript_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.pdf`);
      setError('');
    } catch (err) {
      console.error('PDF export error:', err);
      setError('Failed to generate PDF');
      setTimeout(() => setError(''), 3000);
    }
  };

  const transcribeRecordedAudio = async (audioBlob, language) => {
    setTranscribing(true);
    setError('');
    try {
      const file = new File([audioBlob], `speech_${Date.now()}.wav`, { type: 'audio/wav' });
      const formData = new FormData();
      formData.append('file', file);
      formData.append('language', language);

      const response = await api.post('/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (response.data.success) {
        const text = response.data.text || '';
        fullTextRef.current = text;
        setFullText(text);
        updateTextStats(text);
        if (response.data.summary) {
          setSummary(response.data.summary);
          setSummaryType(response.data.summary_metrics?.type || '');
          setSummaryCompression(parseInt(response.data.summary_metrics?.compression) || 0);
          setSummaryOriginalWords(response.data.summary_metrics?.original_words || 0);
          setSummarySummaryWords(response.data.summary_metrics?.summary_words || 0);
        }
        if (response.data.key_points) {
          setKeyPoints(response.data.key_points);
        }
      } else {
        setError((response.data.error || 'Transcription failed') + ' — keeping the live preview text.');
        setTimeout(() => setError(''), 4000);
      }
    } catch (err) {
      console.error('Backend transcription error:', err);
      setError('Could not reach the transcription server — keeping the live preview text.');
      setTimeout(() => setError(''), 4000);
    } finally {
      setTranscribing(false);
    }
  };

  const startRecording = async () => {
    if (!languageSelected || !selectedLanguage) {
      setError('⚠️ Please select a language first');
      setTimeout(() => setError(''), 3000);
      return;
    }

    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionAPI) {
      setError('Browser not supported. Please use Chrome, Edge, or Safari.');
      setTimeout(() => setError(''), 3000);
      return;
    }

    setFullText('');
    setInterimText('');
    setWordCount(0);
    setCharCount(0);
    setSeconds(0);
    setSummary('');
    setKeyPoints([]);
    setSaved(false);
    setAudioUrl(null);
    setAudioChunks([]);
    audioChunksRef.current = [];
    fullTextRef.current = '';
    interimTextRef.current = '';
    isFinalizingRef.current = false;
    isRecognitionActiveRef.current = false;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];
      
      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorderRef.current.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        const url = URL.createObjectURL(audioBlob);
        setAudioUrl(url);
        setAudioChunks([...audioChunksRef.current]);
        // The live captions above come from the browser's built-in speech
        // recognition, which doesn't support Kinyarwanda and produces no
        // punctuation. Re-transcribe the actual recorded audio through the
        // backend Whisper model for an accurate, properly paragraphed result.
        if (audioBlob.size > 1000) {
          transcribeRecordedAudio(audioBlob, selectedLanguage);
        }
      };
      
      mediaRecorderRef.current.start(1000);
    } catch (err) {
      setError('Could not access microphone. Please check permissions.');
      setTimeout(() => setError(''), 3000);
      return;
    }

    const recognition = new SpeechRecognitionAPI();
    recognition.lang = selectedLanguage === 'rw' ? 'rw-RW' : 'en-US';
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsRecording(true);
      isRecognitionActiveRef.current = true;
      setSeconds(0);
      setError('');
      
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = setInterval(() => {
        setSeconds(prev => prev + 1);
      }, 1000);
    };

    recognition.onresult = (e) => {
      let interim = '';
      let newFullText = fullTextRef.current;
      
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const transcript = e.results[i][0].transcript;
        if (e.results[i].isFinal) {
          if (newFullText && !newFullText.endsWith(' ') && !newFullText.endsWith('.') && !newFullText.endsWith('?') && !newFullText.endsWith('!')) {
            newFullText += ' ';
          }
          newFullText += transcript;
        } else {
          interim += transcript;
        }
      }
      
      if (newFullText !== fullTextRef.current) {
        fullTextRef.current = newFullText;
        const formattedText = formatTextIntoParagraphs(newFullText);
        setFullText(formattedText);
        updateTextStats(newFullText);
      }
      
      if (interim !== interimTextRef.current) {
        interimTextRef.current = interim;
        setInterimText(interim);
      }
    };

    recognition.onerror = (e) => {
      console.error('Recognition error:', e.error);
      let errorMsg = 'Recognition error';
      if (e.error === 'no-speech') errorMsg = 'No speech detected. Please speak into the microphone.';
      else if (e.error === 'audio-capture') errorMsg = 'Microphone not found. Please check your device.';
      else if (e.error === 'not-allowed') errorMsg = 'Microphone permission denied. Please allow access.';
      else errorMsg = `Error: ${e.error}`;
      
      setError(errorMsg);
      stopRecording();
      setTimeout(() => setError(''), 4000);
    };

    recognition.onend = () => {
      isRecognitionActiveRef.current = false;
      if (isRecording && !isFinalizingRef.current) {
        isFinalizingRef.current = true;
        stopRecording();
      }
    };

    recognition.start();
    recognitionRef.current = recognition;
  };

  const stopRecording = () => {
    setIsRecording(false);
    isFinalizingRef.current = true;
    isRecognitionActiveRef.current = false;
    
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {
        console.log('Recognition already stopped');
      }
      recognitionRef.current = null;
    }
    
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
      mediaRecorderRef.current = null;
    }
    
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    
    setInterimText('');
    interimTextRef.current = '';
    
    setTimeout(() => {
      isFinalizingRef.current = false;
    }, 500);
  };

  const clearText = () => {
    setFullText('');
    setInterimText('');
    setWordCount(0);
    setCharCount(0);
    setSeconds(0);
    setAudioUrl(null);
    setAudioChunks([]);
    setSaved(false);
    setSaveResult(null);
    setSummary('');
    setKeyPoints([]);
    setError('');
    setTranscriptionStats({ sentences: 0, paragraphs: 0, estimatedReadingTime: 0 });
    fullTextRef.current = '';
    interimTextRef.current = '';
    if (isRecording) stopRecording();
  };

  const saveToDatabase = async () => {
    if (!fullText.trim()) {
      setError('No text to save. Please record something first.');
      setTimeout(() => setError(''), 3000);
      return;
    }

    setSaving(true);
    setError('');
    
    try {
      let audioBase64 = null;
      if (audioChunks.length > 0) {
        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        const reader = new FileReader();
        audioBase64 = await new Promise((resolve, reject) => {
          reader.onloadend = () => resolve(reader.result);
          reader.onerror = reject;
          reader.readAsDataURL(audioBlob);
        });
      }

      const response = await api.post('/api/speech/save', {
        text: fullText,
        language: selectedLanguage,
        duration: seconds,
        word_count: wordCount,
        audio: audioBase64,
        summary: summary,
        key_points: keyPoints
      });

      if (response.data.success) {
        setSaved(true);
        setSaveResult(response.data);
        await fetchRecords();
        setError('');
        setTimeout(() => setSaved(false), 3000);
      } else {
        setError(response.data.error || 'Failed to save');
      }
    } catch (err) {
      console.error('Save error:', err);
      setError(err.response?.data?.error || err.message || 'Error saving');
    } finally {
      setSaving(false);
    }
  };

  const deleteRecord = async (id) => {
    if (window.confirm('Delete this record permanently? This action cannot be undone.')) {
      try {
        await api.delete(`/api/speech/record/${id}`);
        await fetchRecords();
        if (selectedRecord?.id === id) {
          setSelectedRecord(null);
          clearText();
        }
      } catch (err) {
        setError('Failed to delete record');
        setTimeout(() => setError(''), 3000);
      }
    }
  };

  const loadRecord = (record) => {
    setSelectedRecord(record);
    setFullText(record.text);
    setSummary(record.summary || '');
    setKeyPoints(record.key_points || []);
    setWordCount(record.word_count || 0);
    setSeconds(record.duration || 0);
    setSelectedLanguage(record.language || 'rw');
    setLanguageSelected(true);
    fullTextRef.current = record.text;
    updateTextStats(record.text);
    if (record.audio_url) {
      setAudioUrl(`${API_URL}${record.audio_url}`);
    }
    setActiveTab('record');
    setError('');
  };

  const exportAsText = () => {
    if (!fullText) return;
    
    const date = new Date().toLocaleString();
    const content = `========================================
   SPEECH TRANSCRIPTION REPORT
========================================

Date: ${date}
Language: ${selectedLanguage === 'rw' ? 'Kinyarwanda' : 'English'}
Duration: ${Math.floor(seconds / 60)}:${(seconds % 60).toString().padStart(2, '0')}
Words: ${wordCount}
Characters: ${charCount}
Sentences: ${transcriptionStats.sentences}
Reading Time: ${transcriptionStats.estimatedReadingTime} min

========================================
         FULL TRANSCRIPTION
========================================

${fullText}

${summary ? `========================================
            AI SUMMARY
========================================

${summary}

Summary Type: ${summaryType}
Compression: ${summaryCompression}% of original
Original: ${summaryOriginalWords || wordCount} words | Summary: ${summarySummaryWords || summary.split(/\s+/).length} words
` : ''}

${keyPoints.length > 0 ? `========================================
           KEY POINTS
========================================

${keyPoints.map(p => `${p.number}. ${p.text}\n   (${p.importance.toUpperCase()} priority)`).join('\n\n')}
` : ''}

========================================
      End of Report
========================================
Generated by AudioText Pro`;
    
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `speech_transcript_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const copyToClipboard = (text, type) => {
    navigator.clipboard.writeText(text);
    setError(`✅ ${type} copied to clipboard!`);
    setTimeout(() => setError(''), 2000);
  };

  const formatTime = (secs) => {
    const mins = Math.floor(secs / 60);
    const remainingSecs = secs % 60;
    return `${mins}:${remainingSecs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="speech-recognition-container">
      <div className="speech-recognition-card">
        <div className="speech-header">
          <button className="back-btn" onClick={onBack}>
            ← Back to Dashboard
          </button>
          <div className="speech-header-content">
            <h1>🎙️ Speech Recognition Studio</h1>
            <p>Real-time transcription • AI Summary • Key Points • Save & Export</p>
          </div>
        </div>

        {/* Helper Steps for New Users */}
        {showHelper && !languageSelected && !fullText && (
          <div className="speech-helper">
            <div className="helper-header">
              <span className="helper-icon">💡</span>
              <span className="helper-title">How to use Speech Recognition</span>
              <button className="helper-close" onClick={() => setShowHelper(false)}>✕</button>
            </div>
            <div className="helper-steps">
              {helperSteps.map((step, index) => (
                <div key={index} className="helper-step">
                  <span className="step-icon">{step.icon}</span>
                  <div className="step-info">
                    <span className="step-title">{step.title}</span>
                    <span className="step-desc">{step.description}</span>
                  </div>
                  {index < helperSteps.length - 1 && <span className="step-arrow">→</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="speech-tabs">
          <button className={`tab ${activeTab === 'record' ? 'active' : ''}`} onClick={() => setActiveTab('record')}>
            🎤 Record & Transcribe
          </button>
          <button className={`tab ${activeTab === 'history' ? 'active' : ''}`} onClick={() => setActiveTab('history')}>
            📜 My Library ({records.length})
          </button>
        </div>

        {error && (
          <div className="speech-error">
            <span>⚠️</span>
            <span>{error}</span>
            <button className="error-close" onClick={() => setError('')}>✕</button>
          </div>
        )}

        {activeTab === 'record' ? (
          <div className="speech-record-area">
            {/* Language Selection */}
            <div className="language-selector-primary">
              <div className="language-selector-header">
                <span className="required-icon">⚠️</span>
                <span className="required-text">Step 1: Select Your Language FIRST (Required)</span>
              </div>
              <div className="language-options-primary">
                <button 
                  className={`lang-option-primary ${selectedLanguage === 'en' ? 'selected' : ''}`}
                  onClick={() => handleLanguageSelect('en')}
                >
                  <span className="lang-flag">🇬🇧</span>
                  <span className="lang-name">English</span>
                  {selectedLanguage === 'en' && <span className="check-icon">✓</span>}
                </button>
                <button 
                  className={`lang-option-primary ${selectedLanguage === 'rw' ? 'selected' : ''}`}
                  onClick={() => handleLanguageSelect('rw')}
                >
                  <span className="lang-flag">🇷🇼</span>
                  <span className="lang-name">Kinyarwanda</span>
                  {selectedLanguage === 'rw' && <span className="check-icon">✓</span>}
                </button>
              </div>
              {!languageSelected && (
                <p className="language-warning">⚠️ You MUST select a language before you can start recording</p>
              )}
              {languageSelected && (
                <p className="language-confirm">✅ Language selected: {selectedLanguage === 'en' ? 'English' : 'Kinyarwanda'} - You can now record</p>
              )}
            </div>

            {/* Recording Controls */}
            <div className="recording-area">
              <div className="recording-header">
                <h4>🎙️ Live Recording</h4>
                <p className="recording-hint">Speak clearly into your microphone</p>
              </div>
              <div className="recording-buttons-row">
                <button 
                  className={`record-btn ${isRecording ? 'recording' : ''} ${!languageSelected ? 'disabled' : ''}`}
                  onClick={startRecording}
                  disabled={!languageSelected}
                >
                  {isRecording ? '🔴 Recording...' : '🎙️ Start Recording'}
                </button>
                
                {isRecording && (
                  <button className="stop-recording-btn" onClick={stopRecording}>
                    <span className="btn-icon">⏹️</span>
                    Stop Recording
                  </button>
                )}
              </div>
              
              {!languageSelected && (
                <p className="disabled-hint">🔒 Select a language first to enable recording</p>
              )}
              
              {isRecording && (
                <>
                  <div className="recording-wave-animation">
                    <span></span><span></span><span></span><span></span><span></span>
                  </div>
                  <div className="recording-status">
                    <div className="recording-status-dot"></div>
                    <span className="recording-status-text">Recording in progress... Click Stop when finished</span>
                  </div>
                </>
              )}

              {transcribing && (
                <div className="recording-status">
                  <div className="recording-status-dot"></div>
                  <span className="recording-status-text">🎙️ Transcribing with AI for accurate results...</span>
                </div>
              )}

              <div className="recording-stats">
                <div className="stat">
                  <span className="stat-icon">⏱️</span>
                  <span className="stat-value">{formatTime(seconds)}</span>
                  <span className="stat-label">Duration</span>
                </div>
                <div className="stat">
                  <span className="stat-icon">📝</span>
                  <span className="stat-value">{wordCount}</span>
                  <span className="stat-label">Words</span>
                </div>
                <div className="stat">
                  <span className="stat-icon">📖</span>
                  <span className="stat-value">{transcriptionStats.sentences}</span>
                  <span className="stat-label">Sentences</span>
                </div>
                <div className="stat">
                  <span className="stat-icon">⏰</span>
                  <span className="stat-value">{transcriptionStats.estimatedReadingTime} min</span>
                  <span className="stat-label">Read Time</span>
                </div>
              </div>
            </div>

            {/* Full Transcription Display */}
            <div className="transcription-box">
              <div className="box-header">
                <h4>📄 Full Transcription</h4>
                <div className="box-actions">
                  <button className="copy-btn" onClick={() => copyToClipboard(fullText, 'Transcription')} disabled={!fullText}>
                    📋 Copy
                  </button>
                  <button className="clear-btn" onClick={clearText}>Clear</button>
                </div>
              </div>
              <div className="transcription-content">
                {fullText ? (
                  <div className="full-transcription">
                    {fullText.split('\n\n').map((paragraph, idx) => (
                      <p key={idx} className="transcription-paragraph">{paragraph}</p>
                    ))}
                  </div>
                ) : (
                  <span className="placeholder">Your spoken words will appear here in real-time...</span>
                )}
                {interimText && <div className="interim-text">{interimText}</div>}
              </div>
            </div>

            {/* Audio Playback */}
            {audioUrl && (
              <div className="audio-playback">
                <h4>▶️ Audio Playback</h4>
                <audio controls src={audioUrl} className="audio-player" />
              </div>
            )}

            {/* Actions */}
            <div className="action-buttons">
              <button className="btn-generate" onClick={generateSummaryAndKeyPoints} disabled={generatingSummary || transcribing || !fullText}>
                {generatingSummary ? '⏳ Generating...' : '✨ Generate Summary & Key Points'}
              </button>
              <button className="btn-export" onClick={exportAsText} disabled={transcribing || !fullText}>
                📝 Export as Text
              </button>
              <button className="btn-pdf" onClick={exportAsPDF} disabled={transcribing || !fullText}>
                📄 Export as PDF
              </button>
              <button className="btn-save" onClick={saveToDatabase} disabled={saving || transcribing || !fullText}>
                💾 {saving ? 'Saving...' : 'Save to Library'}
              </button>
            </div>

            {/* AI Summary Section */}
            {summary && (
              <div className="summary-box">
                <div className="summary-header">
                  <h4>📋 AI Summary</h4>
                  <span className="summary-type-badge">{summaryType}</span>
                  <button className="copy-summary-btn" onClick={() => copyToClipboard(summary, 'Summary')}>
                    📋 Copy
                  </button>
                </div>
                <p>{summary}</p>
                <div className="summary-stats">
                  <span>📊 Original: {summaryOriginalWords || wordCount} words</span>
                  <span>📉 Summary: {summarySummaryWords || summary.split(/\s+/).length} words</span>
                  <span>📈 Compression: {summaryCompression}%</span>
                </div>
              </div>
            )}

            {/* Key Points Section */}
            {keyPoints.length > 0 && (
              <div className="keypoints-box">
                <h4>🔑 Key Points</h4>
                <div className="keypoints-list">
                  {keyPoints.map((point) => (
                    <div key={point.number} className="keypoint-item" style={{ 
                      borderLeftColor: point.importance === 'high' ? '#dc2626' : (point.importance === 'medium' ? '#f59e0b' : '#10b981') 
                    }}>
                      <div className="keypoint-header">
                        <span className="keypoint-number">{point.number}</span>
                        <span className="keypoint-icon">{point.icon}</span>
                        <span className={`keypoint-priority ${point.importance}`}>
                          {point.importance.toUpperCase()} PRIORITY
                        </span>
                      </div>
                      <span className="keypoint-text">{point.text}</span>
                    </div>
                  ))}
                </div>
                <button className="copy-keypoints-btn" onClick={() => copyToClipboard(keyPoints.map(p => `${p.number}. ${p.text}`).join('\n\n'), 'Key Points')}>
                  📋 Copy All Key Points
                </button>
              </div>
            )}

            {/* Success Message */}
            {saved && saveResult && (
              <div className="success-message">
                ✅ Saved to library! Record ID: {saveResult.record_id}
              </div>
            )}
          </div>
        ) : (
          <div className="speech-history-area">
            <div className="history-header">
              <h4>📚 My Library</h4>
              <p className="history-hint">View and manage your saved speech recordings</p>
            </div>
            {records.length === 0 ? (
              <div className="empty-library">
                <div className="empty-icon">📭</div>
                <h3>No recordings yet</h3>
                <p>Start by recording your first speech transcript</p>
              </div>
            ) : (
              <div className="records-list">
                {records.map(record => (
                  <div key={record.id} className="library-card">
                    <div className="library-card-header">
                      <div className="card-info">
                        <span className={`language-tag ${record.language}`}>
                          {record.language === 'rw' ? '🇷🇼 Kinyarwanda' : '🇬🇧 English'}
                        </span>
                        <span className="card-date">{new Date(record.created_at).toLocaleString()}</span>
                      </div>
                      <div className="card-actions">
                        <button className="action-view" onClick={() => loadRecord(record)}>👁️ View</button>
                        <button className="action-delete" onClick={() => deleteRecord(record.id)}>🗑️ Delete</button>
                      </div>
                    </div>
                    <div className="card-preview">
                      {record.text?.substring(0, 150)}...
                    </div>
                    <div className="card-meta">
                      <span>📝 {record.word_count} words</span>
                      <span>⏱️ {record.duration} sec</span>
                      {record.summary && <span>📋 Has Summary</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default SpeechRecognition;