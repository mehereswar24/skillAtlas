"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const COLS = 3;
const ROWS = 3;
const TOTAL_TILES = COLS * ROWS;
const SOLVED_STATE = Array.from({ length: TOTAL_TILES }, (_, i) => i === TOTAL_TILES - 1 ? 0 : i + 1);

export function SlidingPuzzle() {
  // Scrambled 3x3 grid
  const [tiles, setTiles] = useState([1, 5, 2, 4, 8, 3, 7, 6, 0]);
  const [isSolved, setIsSolved] = useState(false);

  const handleTileClick = (index: number) => {
    const emptyIndex = tiles.indexOf(0);
    const row = Math.floor(index / COLS);
    const col = index % COLS;
    const emptyRow = Math.floor(emptyIndex / COLS);
    const emptyCol = emptyIndex % COLS;

    const isAdjacent = Math.abs(row - emptyRow) + Math.abs(col - emptyCol) === 1;

    if (isAdjacent) {
      const newTiles = [...tiles];
      newTiles[emptyIndex] = tiles[index];
      newTiles[index] = 0;
      setTiles(newTiles);
      
      // Check if solved
      if (newTiles.every((val, i) => val === SOLVED_STATE[i])) {
        setIsSolved(true);
      } else {
        setIsSolved(false);
      }
    }
  };

  // Map image to fit the theme "Every skill has a map"
  const imageUrl = "https://images.unsplash.com/photo-1524661135-423995f22d0b?auto=format&fit=crop&q=80&w=800&h=800&sat=-100";

  return (
    <div className="w-full max-w-[400px] mx-auto aspect-square bg-card/20 rounded-3xl border p-2 grid grid-cols-3 grid-rows-3 gap-1 shadow-2xl relative overflow-hidden grayscale">
      {/* Glow effect behind */}
      <div className="absolute inset-0 bg-foreground/5 blur-3xl rounded-full" />
      
      {tiles.map((tile, index) => {
        let bgPos = "";
        if (tile !== 0) {
          const solvedIndex = tile - 1;
          const solvedRow = Math.floor(solvedIndex / COLS);
          const solvedCol = solvedIndex % COLS;
          bgPos = `${(solvedCol / (COLS - 1)) * 100}% ${(solvedRow / (ROWS - 1)) * 100}%`;
        }

        return (
        <motion.div
          layout
          key={tile === 0 ? "empty" : tile}
          onClick={() => handleTileClick(index)}
          className={`relative z-10 flex items-center justify-center rounded-2xl overflow-hidden transition-all duration-300 ${
            tile === 0
              ? isSolved ? "cursor-default" : "bg-transparent cursor-default"
              : "bg-card cursor-none hover:opacity-85 shadow-sm"
          } ${isSolved ? "rounded-none gap-0" : ""}`}
          style={
             tile !== 0 ? {
               backgroundImage: `url(${imageUrl})`,
               backgroundSize: `${COLS * 100}% ${ROWS * 100}%`,
               backgroundPosition: bgPos,
             } : isSolved ? {
               backgroundImage: `url(${imageUrl})`,
               backgroundSize: `${COLS * 100}% ${ROWS * 100}%`,
               backgroundPosition: "100% 100%",
             } : {}
          }
          transition={{ type: "spring", stiffness: 400, damping: 35 }}
        >
          {tile !== 0 && !isSolved && (
             <span className="bg-background/80 backdrop-blur-sm px-4 py-2 rounded-full text-foreground text-base font-bold opacity-0 hover:opacity-100 transition-opacity">
               {tile}
             </span>
          )}
        </motion.div>
      )})}
      
      <AnimatePresence>
        {isSolved && (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="absolute bottom-8 left-0 right-0 text-center z-20 pointer-events-none"
          >
            <span className="bg-foreground text-background px-6 py-3 rounded-full text-base font-bold shadow-lg backdrop-blur-md border border-foreground/20">
              Map Restored!
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
