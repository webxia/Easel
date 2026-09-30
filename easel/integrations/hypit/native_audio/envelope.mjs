// Apply one program-clock envelope without moving, restarting or remixing clips.
// Independent of Hypit imports so the exact operation is locally replayable.
export function duckTrack(track, points) {
  if (!Array.isArray(points) || points.length < 2) throw new Error('Missing music envelope');
  let previous = -1;
  for (const point of points) {
    if (!Number.isSafeInteger(point.sample) || point.sample <= previous ||
        !Number.isFinite(point.gain) || point.gain < 0 || point.gain > 1) {
      throw new Error('Invalid music envelope');
    }
    previous = point.sample;
  }
  return {...track, id: `${track.id}.easel-ducked`, clips: track.clips.map(clip => {
    if (clip.gainEnvelope !== undefined) throw new Error('Music already has an envelope');
    return {...clip, gainEnvelope: points.map(point => ({...point}))};
  })};
}
