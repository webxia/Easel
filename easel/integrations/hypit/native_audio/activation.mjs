import {assertAttributes, assertEmptyElement, canonicalize, createMarkupSurfaceHostFacet,
  sameType, sealGraphFragment, textAttribute} from '@hypit/hypit/author-kit';
import {compositionTypes, sealAudioTrack} from '@hypit/hypit/composition';
import {duckTrack} from './envelope.mjs';

const module = {name: '@easel/audio-mix', version: '1'};
const envelopeType = {module, name: 'Envelope'};
const producer = {module, name: 'duck'};
const inputs = [{name: 'source', type: compositionTypes.audioTrack}, {name: 'points', type: envelopeType}];
const manifest = {format: 'hypit.module@1', ...module,
  dependencies: [{module: compositionTypes.audioTrack.module}],
  types: [{name: envelopeType.name}], capabilities: [],
  producers: [{name: 'duck', inputs, outputs: [{name: 'audio', type: compositionTypes.audioTrack}], needs: []}]};
const fragment = sealGraphFragment({inputs, operations: [{id: 'duck', producer,
  inputs: {source: {kind: 'fragment-input', name: 'source'}, points: {kind: 'fragment-input', name: 'points'}},
  result: {kind: 'output', name: 'audio'}}],
  exports: [{name: 'audio', type: compositionTypes.audioTrack, root: {kind: 'fragment-operation', operation: 'duck'}}]});
const component = {producers: [{producer, handler: ({inputs}) => {
  if (inputs.source.value.kind !== 'inline' || inputs.points.value.kind !== 'inline') {
    throw new Error('Music inputs must be inline');
  }
  const audio = sealAudioTrack(duckTrack(inputs.source.value.value, inputs.points.value.value));
  return {outputs: {audio: {kind: 'inline', value: canonicalize(audio)}}, needs: {}};
}}]};
const handler = ({element, resolveReference}) => {
  assertAttributes(element, ['id', 'source', 'points']); assertEmptyElement(element);
  const id = textAttribute(element, 'id'), raw = element.attributes.source;
  const source = raw?.kind === 'reference' ? resolveReference(raw.path) : undefined;
  if (!source || !sameType(source.type, compositionTypes.audioTrack)) throw new Error('Music source must be an AudioTrack');
  const points = JSON.parse(textAttribute(element, 'points'));
  duckTrack({id, clips: []}, points);
  return {records: [{id: `${id}.points`, type: envelopeType,
    value: {kind: 'inline', value: canonicalize(points)}, range: element.range}], fragments: [fragment],
    components: [{id, fragment: fragment.id, inputs: {source: source.ref, points: {kind: 'record', id: `${id}.points`}},
      outputs: {audio: `${id}.audio`}, range: element.range}], exports: [`${id}.audio`]};
};
const declaration = {name: 'duck', tag: 'Duck', mode: 'structured', outputs: [compositionTypes.audioTrack, envelopeType],
  vocabulary: {summary: 'Easel measured sentence ducking, preserving music playback.',
    attributes: [
      {name: 'id', kind: 'identifier', required: true, summary: 'Output identity.'},
      {name: 'source', kind: 'reference', required: true, accepts: [compositionTypes.audioTrack], summary: 'Original music track.'},
      {name: 'points', kind: 'literal', required: true, summary: 'Verified program sample envelope.'}],
    ports: [{name: 'audio', type: compositionTypes.audioTrack, summary: 'Ducked music.'}]}};
export const hypitPackage = {format: 'hypit.node-package@1', modules: [{manifest}], components: [component],
  hostFacets: [createMarkupSurfaceHostFacet({module, declaration, handler})]};
export default hypitPackage;
