import { useState, useCallback, useRef, useEffect } from 'react';
import type { RevisionItem, TranscriptItem } from '@/types';

export function useAudioSync(items: (RevisionItem | TranscriptItem)[] | undefined) {
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [activeIndex, setActiveIndex] = useState(-1);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const currentItem = items?.[activeIndex] || null;

  const handleTimeUpdate = useCallback(() => {
    if (audioRef.current) {
      const time = audioRef.current.currentTime;
      setCurrentTime(time);

      if (items) {
        const index = items.findIndex(
          item => time >= item.startTime && time < item.endTime
        );
        if (index !== -1 && index !== activeIndex) {
          setActiveIndex(index);
        }
      }
    }
  }, [items, activeIndex]);

  const togglePlay = useCallback(() => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  }, [isPlaying]);

  const seekTo = useCallback((time: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setCurrentTime(time);
    }
  }, []);

  const skipForward = useCallback((seconds: number = 5) => {
    if (audioRef.current) {
      const newTime = Math.min(audioRef.current.currentTime + seconds, audioRef.current.duration || Infinity);
      audioRef.current.currentTime = newTime;
      setCurrentTime(newTime);
    }
  }, []);

  const skipBackward = useCallback((seconds: number = 5) => {
    if (audioRef.current) {
      const newTime = Math.max(audioRef.current.currentTime - seconds, 0);
      audioRef.current.currentTime = newTime;
      setCurrentTime(newTime);
    }
  }, []);

  const changePlaybackRate = useCallback((rate: number) => {
    if (audioRef.current) {
      audioRef.current.playbackRate = rate;
      setPlaybackRate(rate);
    }
  }, []);

  const handleEnded = useCallback(() => {
    setIsPlaying(false);
    setActiveIndex(-1);
  }, []);

  useEffect(() => {
    const audio = audioRef.current;
    if (audio) {
      audio.addEventListener('timeupdate', handleTimeUpdate);
      audio.addEventListener('ended', handleEnded);
      return () => {
        audio.removeEventListener('timeupdate', handleTimeUpdate);
        audio.removeEventListener('ended', handleEnded);
      };
    }
  }, [handleTimeUpdate, handleEnded]);

  return {
    audioRef,
    currentTime,
    isPlaying,
    playbackRate,
    activeIndex,
    currentItem,
    togglePlay,
    seekTo,
    skipForward,
    skipBackward,
    changePlaybackRate,
  };
}
