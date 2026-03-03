import fs from 'fs';
import path from 'path';
import TracksGrid from './TracksGrid';

// Hardcoded core circuits for UI layout (will be dynamic in full backend integration)
const CIRCUITS = [
    { name: "Bahrain International Circuit", country: "Sakhir" },
    { name: "Jeddah Corniche Circuit", country: "Jeddah" },
    { name: "Albert Park Circuit", country: "Melbourne" },
    { name: "Suzuka International Racing Course", country: "Suzuka" },
    { name: "Shanghai International Circuit", country: "Shanghai" },
    { name: "Miami International Autodrome", country: "Miami" },
    { name: "Autodromo Enzo e Dino Ferrari", country: "Imola" },
    { name: "Circuit de Monaco", country: "Monte Carlo" },
    { name: "Circuit Gilles-Villeneuve", country: "Montreal" },
    { name: "Circuit de Barcelona-Catalunya", country: "Catalunya" },
    { name: "Red Bull Ring", country: "Spielberg" },
    { name: "Silverstone Circuit", country: "Silverstone" },
    { name: "Hungaroring", country: "Hungaroring" },
    { name: "Circuit de Spa-Francorchamps", country: "Spa Francorchamps" },
    { name: "Circuit Zandvoort", country: "Zandvoort" },
    { name: "Autodromo Nazionale Monza", country: "Monza" },
    { name: "Baku City Circuit", country: "Baku" },
    { name: "Marina Bay Street Circuit", country: "Singapore" },
    { name: "Circuit of the Americas", country: "Austin" },
    { name: "Autodromo Hermanos Rodriguez", country: "Mexico City" },
    { name: "Autodromo Jose Carlos Pace", country: "Interlagos" },
    { name: "Las Vegas Strip Circuit", country: "Las Vegas" },
    { name: "Lusail International Circuit", country: "Lusail" },
    { name: "Yas Marina Circuit", country: "Yas Marina" }
];

export default function TracksPage() {
    const publicDir = path.join(process.cwd(), 'public');
    const tracksAssetDir = path.join(publicDir, 'assets', 'Circuit');

    const processedTracks = CIRCUITS.map(circuit => {
        let trackPath = null;
        if (fs.existsSync(tracksAssetDir)) {
            const files = fs.readdirSync(tracksAssetDir);

            // Attempt to match by country name (e.g. 'sakhir' vs '2026tracksakhirdetailed.avif')
            const targetTerm = circuit.country.toLowerCase().replace(" ", "");
            const match = files.find(f => f.toLowerCase().includes(targetTerm));

            if (match) {
                trackPath = `/assets/Circuit/${match}`;
            }
        }
        return { ...circuit, trackPath };
    });

    return (
        <div className="flex flex-col gap-8 max-w-7xl mx-auto mb-20 animate-in fade-in duration-700">
            <div className="flex flex-col gap-2 relative z-10">
                <h1 className="text-4xl md:text-5xl font-black tracking-tight text-white italic tracking-tighter" style={{ fontFamily: 'Magneto, cursive, sans-serif' }}>
                    Race Places
                </h1>
                <p className="text-f1-muted text-lg italic tracking-wider font-semibold" style={{ fontFamily: 'Magneto, cursive, sans-serif' }}>Information about the iconic circuits on the calendar.</p>
            </div>

            <TracksGrid tracks={processedTracks} />
        </div>
    );
}
