import {
  DndContext,
  DragEndEvent,
  MouseSensor,
  TouchSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useInvalidateStacks } from "../hooks/useInvalidateStacks";
import type { Task } from "../types";
import { TaskCard } from "./TaskCard";

export type StackRef =
  | { stackDate: string; stackId?: undefined }
  | { stackId: number; stackDate?: undefined };

interface Props {
  tasks: Task[];
  stackRef: StackRef;
  moveTarget: { date: string; label: string } | null;
}

function refKey(ref: StackRef): string {
  return ref.stackDate ?? `id:${ref.stackId}`;
}

export function StackView({ tasks, stackRef, moveTarget }: Props) {
  const invalidateStacks = useInvalidateStacks();
  const [localTasks, setLocalTasks] = useState<Task[] | null>(null);

  // Whenever the parent feeds us a fresh list (tab switch, refetch, etc.),
  // drop any stale optimistic state. Otherwise a pending reorder from one
  // stack could render across a tab change.
  useEffect(() => {
    setLocalTasks(null);
  }, [refKey(stackRef), tasks]);

  const sensors = useSensors(
    // Mouse: tiny distance is enough to disambiguate click from drag.
    useSensor(MouseSensor, { activationConstraint: { distance: 4 } }),
    // Touch: require a brief hold so a vertical finger drag is interpreted
    // as page scroll, not as a task reorder. Without this, drag-and-drop
    // hijacks every swipe on mobile.
    useSensor(TouchSensor, {
      activationConstraint: { delay: 200, tolerance: 6 },
    })
  );

  const reorder = useMutation({
    mutationFn: (orderedIds: number[]) => api.reorder(stackRef, orderedIds),
    onSuccess: () => {
      setLocalTasks(null);
      invalidateStacks();
    },
    onError: () => {
      // Revert: drop the optimistic order so the server's truth shows again.
      setLocalTasks(null);
      invalidateStacks();
    },
  });

  const display = localTasks ?? tasks;

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = display.findIndex((t) => t.id === active.id);
    const newIndex = display.findIndex((t) => t.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const reordered = arrayMove(display, oldIndex, newIndex);
    setLocalTasks(reordered);
    reorder.mutate(reordered.map((t) => t.id));
  };

  if (display.length === 0) {
    return <div className="empty">— stack is empty —</div>;
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={display.map((t) => t.id)}
        strategy={verticalListSortingStrategy}
      >
        <ul className="tasks">
          {display.map((task, idx) => (
            <TaskCard
              key={task.id}
              task={task}
              positionIndex={idx}
              moveTarget={moveTarget}
            />
          ))}
        </ul>
      </SortableContext>
    </DndContext>
  );
}
