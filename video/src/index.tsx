import React from "react";
import {Composition, registerRoot} from "remotion";
import {Reel} from "./Reel";

registerRoot(() => <Composition id="Reel" component={Reel} width={1080} height={1920} fps={30} durationInFrames={900}
  defaultProps={{duration: 30, lines: [], shots: [], sfx: [], voice: "voice.wav", music: "", hook: "", theme: {}} as any}
  calculateMetadata={({props}: any) => ({durationInFrames: Math.ceil(props.duration * 30)})} />);
