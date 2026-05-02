import { useRef, useState, useCallback, useEffect } from 'react';
import { Play, Pause, SkipBack, SkipForward, Volume2 } from 'lucide-react';
import { formatTime } from '@/utils/formatTime';

interface AudioPlayerProps {
  audioUrl?: string;
  onTimeUpdate?: (time: number) => void;
  onActiveIndexChange?: (index: number) => void;
  items?: { startTime: number; endTime: number }[];
}

export function AudioPlayer({ audioUrl, onTimeUpdate, onActiveIndexChange, items }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [volume, setVolume] = useState(1);
  const [playbackRate, setPlaybackRate] = useState(1);

  useEffect(() => {
    if (audioRef.current && audioUrl) {
      audioRef.current.src = audioUrl;
      audioRef.current.load();
    }
  }, [audioUrl]);

  const handleTimeUpdate = useCallback(() => {
    if (audioRef.current) {
      const time = audioRef.current.currentTime;
      setCurrentTime(time);
      onTimeUpdate?.(time);

      if (items) {
        const index = items.findIndex(item => time >= item.startTime && time < item.endTime);
        if (index !== -1) {
          onActiveIndexChange?.(index);
        }
      }
    }
  }, [items, onTimeUpdate, onActiveIndexChange]);

  const handleLoadedMetadata = useCallback(() => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration);
    }
  }, []);

  const handleEnded = useCallback(() => {
    setIsPlaying(false);
  }, []);

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

  const handleSeek = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const time = Number(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setCurrentTime(time);
    }
  }, []);

  const skipBackward = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.currentTime = Math.max(0, audioRef.current.currentTime - 5);
    }
  }, []);

  const skipForward = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.currentTime = Math.min(duration, audioRef.current.currentTime + 5);
    }
  }, [duration]);

  const handleVolumeChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const vol = Number(e.target.value);
    setVolume(vol);
    if (audioRef.current) {
      audioRef.current.volume = vol;
    }
  }, []);

  const handleRateChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const rate = Number(e.target.value);
    setPlaybackRate(rate);
    if (audioRef.current) {
      audioRef.current.playbackRate = rate;
    }
  }, []);

  if (!audioUrl) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-[20px] font-medium text-[#1C1917] mb-4">Audio Player</h3>
        <p className="text-[15px] text-[#A8A29E] text-center py-8">
          Audio URL is not available for this session yet.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <audio
        ref={audioRef}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={handleEnded}
        preload="metadata"
      />

      <div className="flex items-center gap-4 mb-3">
        <button
          onClick={skipBackward}
          className="p-2 hover:bg-[#F5F5F4] rounded-full transition-colors"
        >
          <SkipBack className="w-5 h-5 text-[#1C1917]" />
        </button>

        <button
          onClick={togglePlay}
          className="w-12 h-12 bg-[#1C1917] hover:bg-[#292524] rounded-full flex items-center justify-center transition-colors"
        >
          {isPlaying ? (
            <Pause className="w-5 h-5 text-white" />
          ) : (
            <Play className="w-5 h-5 text-white ml-0.5" />
          )}
        </button>

        <button
          onClick={skipForward}
          className="p-2 hover:bg-[#F5F5F4] rounded-full transition-colors"
        >
          <SkipForward className="w-5 h-5 text-[#1C1917]" />
        </button>

        <div className="flex-1 mx-4">
          <input
            type="range"
            min={0}
            max={duration || 0}
            value={currentTime}
            onChange={handleSeek}
            className="w-full h-1 bg-[#E7E5E4] rounded-full appearance-none cursor-pointer accent-[#1C1917]"
          />
        </div>

        <span className="text-[12px] text-[#A8A29E] font-mono tabular-nums">
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>

        <div className="flex items-center gap-2">
          <Volume2 className="w-4 h-4 text-[#A8A29E]" />
          <input
            type="range"
            min={0}
            max={1}
            step={0.1}
            value={volume}
            onChange={handleVolumeChange}
            className="w-20 h-1 bg-[#E7E5E4] rounded-full appearance-none cursor-pointer accent-[#1C1917]"
          />
        </div>

        <select
          value={playbackRate}
          onChange={handleRateChange}
          className="text-[12px] text-[#78716C] bg-[#F5F5F4] border border-[#E7E5E4] rounded-md px-2 py-1 cursor-pointer"
        >
          {[0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.3, 1.4, 1.5].map(rate => (
            <option key={rate} value={rate}>{rate}x</option>
          ))}
        </select>
      </div>
    </div>
  );
}
