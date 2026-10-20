/* =====================================================================
   LITRPG SERIES PROGRESS - DATA FILE

   This is the only file that needs editing when a book is bought,
   started, finished, or a print date is announced. The page
   (litrpg-progress.html) reads it and draws everything. Counts, group
   headings and the "Next" column are all COMPUTED from this data. Never
   type them in by hand.

   Keep this a plain .js file (not JSON): a <script src> tag works when
   the page is opened straight from disk and when served from the site.

   ---------------------------------------------------------------------
   TOP LEVEL
     asOf        'YYYY-MM-DD'  date this data was last checked. Shown in
                               the "Data as of" stamp. Bump it on every edit.
     started     [ series ]    series with at least one volume read
     unstarted   [ series ]    owned, nothing read yet (shown as the
                               secondary group). To promote a series,
                               move its block from `unstarted` to `started`.

   SERIES FIELDS
     name        required  series title
     author      required  author (add the publisher after a dot if useful)
     note        optional  one short caption shown under the author
     complete    optional  true if the series is finished; adds "complete"
     openEnded   optional  true if the list of volumes is NOT the whole
                           series (nothing announced past the last one).
                           Adds a dashed "+" cell and a "nothing announced
                           past vol N" line. The page never invents a total.
     volumes     required  list of volumes, in reading order

   VOLUME FIELDS  (one volume per line)
     n           required  label on the cell, as text: '1', '2.5', '1-2'
     state       required  one of the values below
     date        optional  'YYYY-MM-DD'. Only with state 'announced'.
                           Leave it out if the date is not announced.
     side        optional  true = side story (dog-eared corner)
     span        optional  2 = one printed book that covers two original
                           volumes (draws a double-width cell and counts
                           as 2 volumes in the total)
     unreleased  optional  true = not published in ANY format yet (only
                           announced). Left out of the "released" count.
     title       optional  book title (hover text and screen readers)
     note        optional  extra hover text

   STATES  (a volume has exactly one)
     'digital'    not in print (ebook / web serial only)
     'announced'  print edition announced, not out yet (add date: if known)
     'print'      in print, not bought
     'bought'     bought, not started
     'reading'    bought, reading now
     'read'       bought and read
     'unknown'    unconfirmed. Drawn as a dashed "?", never counted.

   HOW TO UPDATE
     Bought a volume that is in print:   state: 'print'   ->  'bought'
     Started reading it:                 state: 'bought'  ->  'reading'
     Finished it:                        state: 'reading' ->  'read'
     Print date announced:               state: 'digital' ->  'announced',
                                         and add  date: '2027-01-31'
     Announced book comes out:           state: 'announced' -> 'print'
                                         (remove date; remove unreleased
                                         if it had it)
     A new volume appears in a series:   add one line to that series'
                                         volumes list.
     Then change asOf at the top to today's date.

   Mind the commas: every line in a list ends with a comma. If the page
   shows a red "data problem" box at the top, the message names the
   series and volume to fix.
   ===================================================================== */

window.LITRPG_PROGRESS = {

  asOf: '2026-10-20',

  /* ------------------------------------------------------------------
     STARTED
     ------------------------------------------------------------------ */
  started: [

    {
      name: 'Dungeon Crawler Carl',
      author: 'Matt Dinniman',
      note: 'Book 9 is being split into two published books, 9 and 10. No dates yet.',
      volumes: [
        { n: '1',  state: 'read' },
        { n: '2',  state: 'read' },
        { n: '3',  state: 'read' },
        { n: '4',  state: 'read' },
        { n: '5',  state: 'read' },
        { n: '6',  state: 'read' },
        { n: '7',  state: 'read' },
        { n: '8',  state: 'read' },
        { n: '9',  state: 'announced', unreleased: true },
        { n: '10', state: 'announced', unreleased: true }
      ]
    },

    {
      name: 'He Who Fights With Monsters',
      author: 'Shirtaloon',
      volumes: [
        { n: '1',  state: 'read' },
        { n: '2',  state: 'read' },
        { n: '3',  state: 'announced', date: '2026-11-17', note: 'Moved from Oct 13, 2026' },
        { n: '4',  state: 'announced', date: '2027-02-09' },
        { n: '5',  state: 'announced', date: '2027-04-06' },
        { n: '6',  state: 'digital' },
        { n: '7',  state: 'digital' },
        { n: '8',  state: 'digital' },
        { n: '9',  state: 'digital' },
        { n: '10', state: 'digital' },
        { n: '11', state: 'digital' },
        { n: '12', state: 'digital' },
        { n: '13', state: 'digital' }
      ]
    },

    {
      name: 'Heretical Fishing',
      author: 'Haylock Jobson',
      volumes: [
        { n: '1', state: 'read' },
        { n: '2', state: 'read' },
        { n: '3', state: 'read' },
        { n: '4', state: 'read' },
        { n: '5', state: 'read' },
        { n: '6', state: 'unknown', note: 'Listings exist, but this volume is not confirmed as out. Not counted.' }
      ]
    },

    {
      name: 'The Wandering Inn',
      author: 'pirateaba · HarperCollins print edition',
      note: 'The web serial runs to 10 volumes and is ongoing. HarperCollins splits each web Book into 2 print volumes.',
      openEnded: true,
      volumes: [
        { n: '1', state: 'read' },
        { n: '2', state: 'read' },
        { n: '3', state: 'announced', date: '2026-10-20' },
        { n: '4', state: 'announced', date: '2026-11-10' }
      ]
    },

    {
      name: 'Rune Seeker',
      author: 'J.M. Clarke & C.J. Thompson',
      complete: true,
      volumes: [
        { n: '1', state: 'read' },
        { n: '2', state: 'announced', date: '2027-05-04' },
        { n: '3', state: 'digital' },
        { n: '4', state: 'digital' },
        { n: '5', state: 'digital' },
        { n: '6', state: 'digital' },
        { n: '7', state: 'digital' },
        { n: '8', state: 'digital' }
      ]
    },

    {
      name: 'Awaken Online',
      author: 'Travis Bagwell',
      note: '15 titles. Dog-eared corners are side stories.',
      volumes: [
        { n: '1',   state: 'read',      title: 'Catharsis' },
        { n: '2',   state: 'announced', title: 'Precipice', date: '2027-05-04' },
        { n: '2.5', state: 'digital',   title: 'Retribution', side: true },
        { n: '3',   state: 'digital',   title: 'Evolution' },
        { n: '3.5', state: 'digital',   title: 'Apathy', side: true },
        { n: '4',   state: 'digital',   title: 'Dominion' },
        { n: '4.5', state: 'digital',   title: 'Unity', side: true },
        { n: '5',   state: 'digital',   title: 'Ember' },
        { n: '6',   state: 'digital',   title: 'Flame' },
        { n: '7',   state: 'digital',   title: 'Inferno' },
        { n: '8',   state: 'digital',   title: 'Hellion' },
        /* Sources disagree on whether Happy is a side story. Following the
           agreed order, it is treated as a main volume. */
        { n: '9',   state: 'digital',   title: 'Happy' },
        { n: '10',  state: 'digital',   title: 'Armageddon' },
        { n: '11',  state: 'digital',   title: 'Timeless' },
        { n: '12',  state: 'digital',   title: 'Crucible' }
      ]
    },

    {
      name: "Jake's Magical Market",
      author: 'J.R. Mathews',
      complete: true,
      volumes: [
        { n: '1', state: 'read' },
        { n: '2', state: 'announced', date: '2027-05-11' },
        { n: '3', state: 'digital' }
      ]
    },

    {
      name: 'Rise of Mankind',
      author: 'Jez Cajiao',
      volumes: [
        { n: '1', state: 'read' },
        { n: '2', state: 'announced', date: '2027-07-06' },
        { n: '3', state: 'digital' },
        { n: '4', state: 'digital' },
        { n: '5', state: 'digital' },
        { n: '6', state: 'digital' },
        { n: '7', state: 'digital' },
        { n: '8', state: 'digital' }
      ]
    },

    {
      name: 'Battle Mage Farmer',
      author: 'Seth Ring',
      complete: true,
      volumes: [
        { n: '1', state: 'read' },
        { n: '2', state: 'digital' },
        { n: '3', state: 'digital' },
        { n: '4', state: 'digital' },
        { n: '5', state: 'digital' },
        { n: '6', state: 'digital' },
        { n: '7', state: 'digital' },
        { n: '8', state: 'digital' },
        { n: '9', state: 'digital' }
      ]
    },

    {
      name: 'Mage Errant',
      author: 'John Bierce',
      note: 'The Vault hardcover Book 1 combines original volumes 1 and 2. The original run is 7 volumes.',
      complete: true,
      volumes: [
        { n: '1-2', state: 'read', span: 2, note: 'Vault hardcover Book 1 = original volumes 1 and 2' },
        { n: '3',   state: 'digital' },
        { n: '4',   state: 'digital' },
        { n: '5',   state: 'digital' },
        { n: '6',   state: 'digital' },
        { n: '7',   state: 'digital' }
      ]
    },

    {
      name: 'The Divine Dungeon',
      author: 'Dakota Krout',
      complete: true,
      volumes: [
        { n: '1', state: 'read' },
        { n: '2', state: 'read' },
        { n: '3', state: 'reading' },
        { n: '4', state: 'bought' },
        { n: '5', state: 'bought' }
      ]
    }

  ],

  /* ------------------------------------------------------------------
     OWNED, NOT YET STARTED
     ------------------------------------------------------------------ */
  unstarted: [

    {
      name: 'Cradle',
      author: 'Will Wight',
      complete: true,
      volumes: [
        { n: '1',  state: 'bought' },
        { n: '2',  state: 'bought' },
        { n: '3',  state: 'bought' },
        { n: '4',  state: 'print' },
        { n: '5',  state: 'print' },
        { n: '6',  state: 'print' },
        { n: '7',  state: 'print' },
        { n: '8',  state: 'print' },
        { n: '9',  state: 'print' },
        { n: '10', state: 'print' },
        { n: '11', state: 'print' },
        { n: '12', state: 'print' }
      ]
    },

    {
      name: 'Beware of Chicken',
      author: 'Casualfarmer · Podium',
      volumes: [
        { n: '1', state: 'bought' },
        { n: '2', state: 'print' },
        { n: '3', state: 'print' },
        { n: '4', state: 'bought' },
        { n: '5', state: 'bought' },
        { n: '6', state: 'announced', date: '2027-06-22', unreleased: true }
      ]
    },

    {
      name: 'Apocalypse Parenting',
      author: 'Erin Ampersand',
      complete: true,
      volumes: [
        { n: '1', state: 'bought',    title: 'Time to Play' },
        { n: '2', state: 'announced', date: '2026-11-10' },
        { n: '3', state: 'announced', date: '2027-02-16' },
        { n: '4', state: 'announced', date: '2027-05-18' },
        { n: '5', state: 'announced', date: '2027-08-24' }
      ]
    },

    {
      name: 'The Sigilist',
      author: 'Django Wexler · Orbit',
      note: 'Orbit. Series length not yet known.',
      openEnded: true,
      volumes: [
        { n: '1', state: 'bought', note: 'The Only Way Out Is Up — Orbit trade paperback, released Sep 29, 2026' }
      ]
    }

  ]
};
