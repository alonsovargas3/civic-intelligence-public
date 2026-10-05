import WhoOwnsAustin from './WhoOwnsAustin.jsx'
import HomesteadCap from './HomesteadCap.jsx'
import InvestorComplaints from './InvestorComplaints.jsx'
import CityDollars from './CityDollars.jsx'
import BallotMoney from './BallotMoney.jsx'
import MoneyWins from './MoneyWins.jsx'
import TrafficDeaths from './TrafficDeaths.jsx'
import HomeBuilders from './HomeBuilders.jsx'
import ServiceEquity from './ServiceEquity.jsx'
import LocalMoney from './LocalMoney.jsx'
import WhoPays from './WhoPays.jsx'
import MoneyInfluence from './MoneyInfluence.jsx'
import DistrictDivide from './DistrictDivide.jsx'
import CouncilDissent from './CouncilDissent.jsx'
import ShortTermRentals from './ShortTermRentals.jsx'
import StrGap from './StrGap.jsx'
import WhoLobbies from './WhoLobbies.jsx'
import AnimalShelter from './AnimalShelter.jsx'
import FoodInspections from './FoodInspections.jsx'

/* Story registry. `Component: null` = planned but not yet built (shown dimmed in
   the index). The router renders Component for any slug whose Component is set. */
export const STORIES = [
  {
    slug: 'animal-shelter',
    eyebrow: 'City services · Animals',
    title: "Austin Animal Center outcomes",
    dek: "Intakes and outcomes at Austin Animal Center, including the live-release rate.",
    status: 'published',
    Component: AnimalShelter,
  },
  {
    slug: 'food-inspections',
    eyebrow: 'City services · Food safety',
    title: "Austin food inspection scores",
    dek: "How Austin food-establishment inspection visits score, by band, with missing-score accounting.",
    status: 'published',
    Component: FoodInspections,
  },
  {
    slug: 'who-owns-austin',
    eyebrow: 'Property · Ownership',
    title: "Who Owns Austin",
    dek: "Property ownership on the Travis County appraisal roll, by owner type.",
    status: 'published',
    Component: WhoOwnsAustin,
  },
  {
    slug: 'homestead-cap',
    eyebrow: 'Property · Taxes',
    title: "The homestead cap",
    dek: "How the residence-homestead cap affects taxable value across Austin homes.",
    status: 'published',
    Component: HomesteadCap,
  },
  {
    slug: 'short-term-rentals',
    eyebrow: 'Housing · Rentals',
    title: "Austin's licensed short-term rentals",
    dek: "Licensed short-term rentals by license type and location.",
    status: 'published',
    Component: ShortTermRentals,
  },
  {
    slug: 'str-gap',
    eyebrow: 'Housing · Rentals',
    title: "Short-term rental listings and licenses",
    dek: "Compares Inside Airbnb listings with City of Austin short-term rental licenses.",
    status: 'published',
    Component: StrGap,
  },
  {
    slug: 'investor-single-family',
    eyebrow: 'Property · Code',
    title: "Code complaints by owner type",
    dek: "Code-complaint rates for single-family homes by owner type, compared within property class.",
    status: 'published',
    Component: InvestorComplaints,
  },
  {
    slug: 'traffic-deaths',
    eyebrow: 'Safety · Vision Zero',
    title: "Traffic crashes and deaths",
    dek: "Crash and traffic-fatality trends from City of Austin crash records.",
    status: 'published',
    Component: TrafficDeaths,
  },
  {
    slug: 'who-lobbies',
    eyebrow: 'Influence · Lobbying',
    title: "Who lobbies City Hall",
    dek: "Registered lobbyists, their clients and reported compensation, by industry.",
    status: 'published',
    Component: WhoLobbies,
  },
  {
    slug: 'council-dissent',
    eyebrow: 'Governance · Council',
    title: "Austin City Council voting patterns",
    dek: "Council vote outcomes and dissent, by member and topic.",
    status: 'published',
    Component: CouncilDissent,
  },
  {
    slug: 'money-influence',
    eyebrow: 'Money · Influence',
    title: "Campaign money, votes and contracts",
    dek: "Screens for links between campaign contributions, council votes and city contracts.",
    status: 'published',
    Component: MoneyInfluence,
  },
  {
    slug: 'ballot-money',
    eyebrow: 'Money · Elections',
    title: "Who funds Austin's ballot campaigns",
    dek: "Contributions to ballot-measure committees and their largest funders.",
    status: 'published',
    Component: BallotMoney,
  },
  {
    slug: 'money-wins',
    eyebrow: 'Money · Elections',
    title: "Campaign fundraising and ballot outcomes",
    dek: "Compares committee fundraising with results in contested Austin ballot measures.",
    status: 'published',
    Component: MoneyWins,
  },
  {
    slug: 'home-builders',
    eyebrow: 'Growth · Housing',
    title: "Who's building Austin's homes",
    dek: "New-home construction permits, by builder.",
    status: 'published',
    Component: HomeBuilders,
  },
  {
    slug: 'district-divide',
    eyebrow: 'Equity · Districts',
    title: "Council district demographics and services",
    dek: "Income, race, crime reports and 311 response, by council district.",
    status: 'published',
    Component: DistrictDivide,
  },
  {
    slug: 'service-equity',
    eyebrow: 'Civic services · 311',
    title: "311 response times by district",
    dek: "311 time-to-close by council district, adjusted for request mix.",
    status: 'published',
    Component: ServiceEquity,
  },
  {
    slug: 'local-money',
    eyebrow: 'Money · Elections',
    title: "Where Austin campaign money comes from",
    dek: "In-state and out-of-state shares of contributions to candidates and ballot committees.",
    status: 'published',
    Component: LocalMoney,
  },
  {
    slug: 'who-pays',
    eyebrow: 'Money · Elections',
    title: "Who pays for Austin politics",
    dek: "How Austin campaign contributions are distributed by gift size.",
    status: 'published',
    Component: WhoPays,
  },
  {
    slug: 'where-city-dollars-go',
    eyebrow: 'Money · Spending',
    title: "Where city dollars go",
    dek: "City of Austin checkbook payments, by vendor and category.",
    status: 'published',
    Component: CityDollars,
  },
]

export const STORY_BY_SLUG = Object.fromEntries(STORIES.map((s) => [s.slug, s]))
