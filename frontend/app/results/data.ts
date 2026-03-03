import { TEAM_THEMES, TeamName } from '../constants/themes';

export interface PodiumFinish {
    pos: number;
    driver: string;
    team: TeamName;
}

export interface RaceResult {
    race: string;
    date: string;
    location: string;
    podium: PodiumFinish[];
}

export const RECENT_RESULTS: RaceResult[] = [];

export const HISTORICAL_SEASONS = [
    {
        year: 2025,
        results: [
            {
                race: "Abu Dhabi Grand Prix (2025)", date: "Dec 07, 2025", location: "Yas Marina",
                podium: [
                    { pos: 1, driver: "Max Verstappen", team: "Red Bull Racing" as TeamName },
                    { pos: 2, driver: "Charles Leclerc", team: "Ferrari" as TeamName },
                    { pos: 3, driver: "Lando Norris", team: "McLaren" as TeamName }
                ]
            },
            {
                race: "Qatar Grand Prix (2025)", date: "Nov 30, 2025", location: "Lusail",
                podium: [
                    { pos: 1, driver: "Max Verstappen", team: "Red Bull Racing" as TeamName },
                    { pos: 2, driver: "George Russell", team: "Mercedes" as TeamName },
                    { pos: 3, driver: "Oscar Piastri", team: "McLaren" as TeamName }
                ]
            }
        ]
    },
    {
        year: 2024,
        results: [
            {
                race: "Abu Dhabi Grand Prix (2024)", date: "Dec 08, 2024", location: "Yas Marina",
                podium: [
                    { pos: 1, driver: "Lando Norris", team: "McLaren" as TeamName },
                    { pos: 2, driver: "Carlos Sainz", team: "Ferrari" as TeamName },
                    { pos: 3, driver: "Charles Leclerc", team: "Ferrari" as TeamName }
                ]
            }
        ]
    },
    {
        year: 2023,
        results: [
            {
                race: "Abu Dhabi Grand Prix (2023)", date: "Nov 26, 2023", location: "Yas Marina",
                podium: [
                    { pos: 1, driver: "Max Verstappen", team: "Red Bull Racing" as TeamName },
                    { pos: 2, driver: "Charles Leclerc", team: "Ferrari" as TeamName },
                    { pos: 3, driver: "George Russell", team: "Mercedes" as TeamName }
                ]
            }
        ]
    },
    {
        year: 2022,
        results: [
            {
                race: "Abu Dhabi Grand Prix (2022)", date: "Nov 20, 2022", location: "Yas Marina",
                podium: [
                    { pos: 1, driver: "Max Verstappen", team: "Red Bull Racing" as TeamName },
                    { pos: 2, driver: "Charles Leclerc", team: "Ferrari" as TeamName },
                    { pos: 3, driver: "Sergio Perez", team: "Red Bull Racing" as TeamName }
                ]
            }
        ]
    },
    {
        year: 2021,
        results: [
            {
                race: "Abu Dhabi Grand Prix (2021)", date: "Dec 12, 2021", location: "Yas Marina",
                podium: [
                    { pos: 1, driver: "Max Verstappen", team: "Red Bull Racing" as TeamName },
                    { pos: 2, driver: "Lewis Hamilton", team: "Mercedes" as TeamName },
                    { pos: 3, driver: "Carlos Sainz", team: "Ferrari" as TeamName }
                ]
            }
        ]
    },
    {
        year: 2020,
        results: [
            {
                race: "Abu Dhabi Grand Prix (2020)", date: "Dec 13, 2020", location: "Yas Marina",
                podium: [
                    { pos: 1, driver: "Max Verstappen", team: "Red Bull Racing" as TeamName },
                    { pos: 2, driver: "Valtteri Bottas", team: "Mercedes" as TeamName },
                    { pos: 3, driver: "Lewis Hamilton", team: "Mercedes" as TeamName }
                ]
            }
        ]
    },
    {
        year: 2019,
        results: [
            {
                race: "Abu Dhabi Grand Prix (2019)", date: "Dec 01, 2019", location: "Yas Marina",
                podium: [
                    { pos: 1, driver: "Lewis Hamilton", team: "Mercedes" as TeamName },
                    { pos: 2, driver: "Max Verstappen", team: "Red Bull Racing" as TeamName },
                    { pos: 3, driver: "Charles Leclerc", team: "Ferrari" as TeamName }
                ]
            }
        ]
    },
    {
        year: 2018,
        results: [
            {
                race: "Abu Dhabi Grand Prix (2018)", date: "Nov 25, 2018", location: "Yas Marina",
                podium: [
                    { pos: 1, driver: "Lewis Hamilton", team: "Mercedes" as TeamName },
                    { pos: 2, driver: "Sebastian Vettel", team: "Ferrari" as TeamName },
                    { pos: 3, driver: "Max Verstappen", team: "Red Bull Racing" as TeamName }
                ]
            }
        ]
    }
];
