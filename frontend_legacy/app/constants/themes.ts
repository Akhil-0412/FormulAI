export const TEAM_THEMES = {
    "Red Bull Racing": {
        primary: "#0600EF",
        accent: "#E80020",
        gradient: "from-[#0600EF] to-[#E80020]",
        border: "border-l-[#0600EF]",
        glow: "shadow-[#0600EF]/20"
    },
    "Ferrari": {
        primary: "#E80020",
        accent: "#FFFFFF",
        gradient: "from-[#E80020] to-[#FF2800]",
        border: "border-l-[#E80020]",
        glow: "shadow-[#E80020]/20"
    },
    "Mercedes": {
        primary: "#00D2BE",
        accent: "#FFFFFF",
        gradient: "from-[#00D2BE] to-[#27F4D2]",
        border: "border-l-[#00D2BE]",
        glow: "shadow-[#00D2BE]/20"
    },
    "McLaren": {
        primary: "#FF8700",
        accent: "#000000",
        gradient: "from-[#FF8700] to-[#FFB347]",
        border: "border-l-[#FF8700]",
        glow: "shadow-[#FF8700]/20"
    },
    "Aston Martin": {
        primary: "#229971",
        accent: "#CEDC00",
        gradient: "from-[#229971] to-[#006F62]",
        border: "border-l-[#229971]",
        glow: "shadow-[#229971]/20"
    },
    "Alpine": {
        primary: "#0093CC",
        accent: "#FF87BC",
        gradient: "from-[#0093CC] to-[#FF87BC]",
        border: "border-l-[#0093CC]",
        glow: "shadow-[#0093CC]/20"
    },
    "Williams": {
        primary: "#64C4FF",
        accent: "#FFFFFF",
        gradient: "from-[#64C4FF] to-[#005AFF]",
        border: "border-l-[#64C4FF]",
        glow: "shadow-[#64C4FF]/20"
    },
    "Haas": {
        primary: "#B6BABD",
        accent: "#E60000",
        gradient: "from-[#B6BABD] to-[#E60000]",
        border: "border-l-[#FFFFFF]",
        glow: "shadow-white/10"
    },
    "RB": {
        primary: "#6692FF",
        accent: "#FFFFFF",
        gradient: "from-[#6692FF] to-[#0000FF]",
        border: "border-l-[#6692FF]",
        glow: "shadow-[#6692FF]/20"
    },
    "Audi": {
        primary: "#000000",
        accent: "#FF0000",
        gradient: "from-[#111111] to-[#FF0000]",
        border: "border-l-[#FF0000]",
        glow: "shadow-red-500/20"
    },
    "Cadillac": {
        primary: "#C0C0C0",
        accent: "#000000",
        gradient: "from-[#C0C0C0] to-[#333333]",
        border: "border-l-[#C0C0C0]",
        glow: "shadow-white/10"
    }
};

export type TeamName = keyof typeof TEAM_THEMES;
