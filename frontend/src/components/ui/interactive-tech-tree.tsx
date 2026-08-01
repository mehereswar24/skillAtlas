"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Lock, Zap, Database, Globe, Cpu, RotateCcw, Box } from "lucide-react";

const SKILLS = [
  { id: 1, name: "Logic & Proofs", icon: Box },
  { id: 2, name: "Data Structures", icon: Database },
  { id: 3, name: "Algorithms", icon: Cpu },
  { id: 4, name: "Distributed Systems", icon: Globe },
];

export function InteractiveTechTree() {
  const [completed, setCompleted] = useState<number[]>([]);

  const handleNodeClick = (id: number) => {
    const isAvailable = id === 1 || completed.includes(id - 1);
    
    if (completed.includes(id)) {
       // Toggle off (and all descendants)
       setCompleted(completed.filter(n => n < id));
    } else if (isAvailable) {
       setCompleted([...completed, id]);
    }
  };

  return (
    <div className="w-full max-w-sm mx-auto flex flex-col py-8 px-8 bg-card border rounded-3xl shadow-2xl relative grayscale">
      <div className="flex items-center justify-between mb-8">
        <h3 className="font-display font-semibold text-lg tracking-tight">Interactive Map</h3>
        <button onClick={() => setCompleted([])} className="text-muted-foreground hover:text-foreground transition-colors cursor-none" title="Reset">
           <RotateCcw className="w-4 h-4" />
        </button>
      </div>

      <div className="relative flex flex-col gap-10">
        {/* SVG line in background */}
        <div className="absolute left-6 top-6 bottom-6 w-0.5 bg-muted">
          <motion.div 
            className="w-full bg-foreground"
            initial={{ height: "0%" }}
            animate={{ height: `${(Math.max(0, completed.length - (completed.length === SKILLS.length ? 0 : 1)) / (SKILLS.length - 1)) * 100}%` }}
            transition={{ duration: 0.5, ease: "easeInOut" }}
          />
        </div>

        {SKILLS.map((skill, index) => {
          const isCompleted = completed.includes(skill.id);
          const isAvailable = skill.id === 1 || completed.includes(skill.id - 1);
          const isLocked = !isCompleted && !isAvailable;
          const Icon = skill.icon;

          return (
            <motion.div 
              key={skill.id}
              className={`relative z-10 flex items-center gap-6 ${isLocked ? "opacity-50" : "opacity-100"}`}
            >
              <button
                onClick={() => handleNodeClick(skill.id)}
                disabled={isLocked}
                className={`flex-shrink-0 flex items-center justify-center w-12 h-12 rounded-full border-2 transition-all duration-300 cursor-none ${
                  isCompleted 
                    ? "bg-foreground border-foreground text-background scale-110 shadow-lg" 
                    : isAvailable 
                      ? "bg-background border-foreground text-foreground hover:bg-muted/50 scale-100" 
                      : "bg-muted border-muted text-muted-foreground scale-95"
                }`}
              >
                {isLocked ? <Lock className="w-5 h-5" /> : <Icon className="w-5 h-5" />}
              </button>
              
              <div className="flex flex-col cursor-default select-none">
                <span className={`font-semibold font-display tracking-tight transition-colors duration-300 ${isCompleted ? "text-foreground" : isAvailable ? "text-foreground" : "text-muted-foreground"}`}>
                  {skill.name}
                </span>
                <span className="text-xs text-muted-foreground mt-0.5">
                  {isCompleted ? "Node mastered" : isAvailable ? "Available to learn" : "Locked prerequisite"}
                </span>
              </div>
            </motion.div>
          );
        })}
      </div>
      
      <AnimatePresence>
        {completed.length === SKILLS.length && (
          <motion.div
             initial={{ opacity: 0, y: 10, scale: 0.9 }}
             animate={{ opacity: 1, y: 0, scale: 1 }}
             exit={{ opacity: 0, y: -10, scale: 0.9 }}
             className="absolute -bottom-4 right-6 bg-foreground text-background px-4 py-2 rounded-full text-xs font-bold shadow-xl flex items-center gap-2 border-2 border-background"
          >
             <Zap className="w-3 h-3" />
             Route Mastered
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
