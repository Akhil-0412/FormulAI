"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import { motion, AnimatePresence, useMotionValue, useTransform, animate } from "framer-motion";
import { X } from "lucide-react";

export default function TracksGrid({ tracks }: { tracks: any[] }) {
    const [selectedTrack, setSelectedTrack] = useState<any>(null);

    const progress = useMotionValue(0);
    const maskImage = useTransform(
        progress,
        (p) => `conic-gradient(from 0deg at 50% 50%, black ${p}deg, transparent ${p}deg)`
    );

    useEffect(() => {
        if (selectedTrack) {
            progress.set(0);
            animate(progress, 360, { duration: 2.5, ease: "easeInOut" });
        }
    }, [selectedTrack, progress]);

    // Lock body scroll when modal is open
    useEffect(() => {
        if (selectedTrack) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = 'unset';
        }
        return () => { document.body.style.overflow = 'unset'; };
    }, [selectedTrack]);

    return (
        <>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 relative z-10">
                {tracks.map((track) => (
                    <motion.div
                        key={track.name}
                        layoutId={`card-${track.name}`}
                        className="glass-card p-6 flex flex-col group min-h-[300px] cursor-pointer"
                        onClick={() => setSelectedTrack(track)}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                    >
                        <div className="mb-4 text-center">
                            <h3 className="text-xl font-bold text-white mb-1 group-hover:text-f1-red transition-colors">{track.country}</h3>
                            <p className="text-sm text-f1-muted">{track.name}</p>
                        </div>

                        <motion.div layoutId={`img-container-${track.name}`} className="flex-1 flex items-center justify-center p-4 pointer-events-none">
                            {track.trackPath ? (
                                <div className="relative w-full h-[180px]">
                                    <Image
                                        src={track.trackPath}
                                        alt={track.name}
                                        fill
                                        className="object-contain drop-shadow-[0_10px_15px_rgba(0,0,0,0.5)] group-hover:scale-105 transition-transform duration-500"
                                        unoptimized
                                    />
                                </div>
                            ) : (
                                <div className="text-center opacity-30 text-white">
                                    <span className="text-4xl block mb-2">🗺️</span>
                                    <span className="text-xs">Layout Not Available</span>
                                </div>
                            )}
                        </motion.div>
                    </motion.div>
                ))}
            </div>

            <AnimatePresence>
                {selectedTrack && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="absolute inset-0 bg-f1-navy/90 backdrop-blur-md"
                            onClick={() => setSelectedTrack(null)}
                        />

                        <motion.div
                            layoutId={`card-${selectedTrack.name}`}
                            className="glass-panel relative w-full max-w-5xl h-[80vh] p-8 md:p-12 rounded-3xl z-10 flex flex-col items-center border border-white/20 shadow-2xl overflow-hidden"
                        >
                            <button
                                onClick={() => setSelectedTrack(null)}
                                className="absolute top-6 right-6 p-3 rounded-full bg-white/10 hover:bg-white/20 text-white transition-colors z-20"
                            >
                                <X className="w-6 h-6" />
                            </button>

                            <motion.div
                                initial={{ opacity: 0, y: -20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.3 }}
                                className="text-center mb-8 relative z-20"
                            >
                                <h2 className="text-4xl md:text-5xl font-black text-white mb-2">{selectedTrack.country}</h2>
                                <p className="text-f1-muted text-xl">{selectedTrack.name}</p>
                            </motion.div>

                            <div className="relative w-full flex-1 flex items-center justify-center p-4">
                                {selectedTrack.trackPath ? (
                                    <motion.div
                                        layoutId={`img-container-${selectedTrack.name}`}
                                        className="relative w-full h-full"
                                        style={{
                                            WebkitMaskImage: maskImage,
                                            maskImage: maskImage,
                                        }}
                                    >
                                        <Image
                                            src={selectedTrack.trackPath}
                                            alt={selectedTrack.name}
                                            fill
                                            className="object-contain drop-shadow-[0_0_30px_rgba(232,0,32,0.3)]"
                                            unoptimized
                                        />
                                    </motion.div>
                                ) : (
                                    <div className="text-center opacity-30 text-white">
                                        <span className="text-6xl block mb-4">🗺️</span>
                                        <span>Layout Not Available</span>
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
        </>
    );
}
