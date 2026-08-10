import type { JSX } from "react";
import ChoiceExercise from "./ChoiceExercise";
import MatchingExercise from "./MatchingExercise";
import SequencingExercise from "./SequencingExercise";
import TracingExercise from "./TracingExercise";
import type { ExerciseProps } from "./common";

// The pluggable renderer registry: adding a new exercise type means writing
// one component and registering it here — ExercisePlayer never switches on
// the type directly.
const RENDERERS: Record<string, (props: ExerciseProps) => JSX.Element> = {
  choice: (props) => <ChoiceExercise {...props} />,
  matching: (props) => <MatchingExercise {...props} />,
  sequencing: (props) => <SequencingExercise {...props} />,
  tracing: (props) => <TracingExercise {...props} />,
};

export default function ExerciseRenderer(props: ExerciseProps) {
  const Renderer = RENDERERS[props.exercise.type] ?? RENDERERS.choice;
  return <Renderer {...props} />;
}
