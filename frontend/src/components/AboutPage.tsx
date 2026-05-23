/**
 * About / vision page. Mono-styled long-form prose; same typography rules as
 * the rest of the app. Reachable from the topbar nav.
 */
export function AboutPage() {
  return (
    <article className="about">
      <header className="about__hero">
        <div className="about__eyebrow">About Stack</div>
        <h1 className="about__title">
          Priority is a queue, not a list.
        </h1>
        <p className="about__lede">
          Most to-do apps treat your work as a flat list of equal items. They
          ignore the truth — there's one thing on top, the rest are queued,
          and the order changes every time something new lands in your inbox.
          Stack is built around that truth.
        </p>
      </header>

      <section className="about__section">
        <div className="about__section-label">The idea</div>
        <p>
          One item is on top — the next thing you're doing. When something
          more urgent comes in, it goes on top and everything else shifts
          down a notch. When you finish what's on top, the next item is
          automatically up.
        </p>
        <p>
          The whole product is a discipline around making that easy: capture
          fast, reorder fast, see the top clearly, ignore the rest until the
          top is done.
        </p>
      </section>

      <section className="about__section">
        <div className="about__section-label">Priority is contextual</div>
        <p>
          The same item changes importance based on what else is on your
          plate. A cookbook can sit at #8 in your Reading stack for months
          — interesting enough to get to eventually. The moment your Today
          stack has <em>make pasta from scratch tonight</em> on top, that
          same cookbook just became the most important thing in Reading.
        </p>
        <p>
          The book didn't change — you did. Stack is built so priority can
          shift accordingly: items in one stack can be promoted because
          something on top of another stack just demanded it. The order of
          every stack is alive, not frozen at the moment you added the
          item.
        </p>
      </section>

      <section className="about__section">
        <div className="about__section-label">How it works today</div>

        <h2 className="about__sub">Daily stacks</h2>
        <p>
          One per day, identified by date. Today, Tomorrow. This is your
          commitment — what you're doing <em>now</em>, what's queued for
          tomorrow. The top of the stack is rendered larger than the rest, on
          purpose. You should feel the weight of the one thing that's next.
        </p>

        <h2 className="about__sub">Topic stacks</h2>
        <p>
          Evergreen lists by theme — Reading, Watching, Listening, Buy,
          Ideas, To-Do. These don't have dates. They're the long backlogs
          you pull from. A book lives in your Reading stack until the day
          you decide to actually read it, at which point you pull it into
          Today.
        </p>

        <h2 className="about__sub">Live timers</h2>
        <p>
          Hit play on the thing you're working on. The timer keeps counting
          even when the tab is closed, because the elapsed time is computed
          from the server-side start timestamp — not from a frontend
          stopwatch. Mark it done and the time gets archived with the task.
        </p>

        <h2 className="about__sub">Move, don't copy</h2>
        <p>
          Tasks live in exactly one stack at a time. Pulling from Reading
          into Today is a <em>move</em>, not a duplicate. There's no version
          drift, no "did I already mark this done somewhere else."
        </p>
      </section>

      <section className="about__section">
        <div className="about__section-label">Where this is going</div>

        <h2 className="about__sub">Shareable stacks</h2>
        <p>
          Your reading list shouldn't be trapped in a private app. The plan:
          mark any topic stack public and get a shareable URL. Friends can
          browse your Sci-Fi reading stack the same way they'd browse a
          Goodreads list — but with priority order baked in, because order
          is meaningful (the top is what you'll read next, not just a flat
          set).
        </p>
        <p>
          Social discovery comes from this: "what's on Aryan's reading stack
          right now?" — a more honest signal than a starred-favorites list.
        </p>

        <h2 className="about__sub">An AI stack agent</h2>
        <p>
          Today you wrote <em>make pasta from scratch tonight</em> at the
          top of your Today stack. Your Reading stack has thirty books; an
          Italian cookbook sits at #8 — too far down to notice.
        </p>
        <p>
          The agent reads across all your stacks, notices the overlap, and
          asks: <em>"You're making pasta tonight. Move the cookbook to the
          top of Reading?"</em> You hit yes; next time you open Reading,
          the relevant thing is the first thing you see.
        </p>
        <p>
          That's the core move — the agent treats priority as a function
          of what you're focused on right now, not a static label. Same
          logic for context drops ("the trip got pushed a week", "I'm
          sick tomorrow") and for time windows ("I have two free hours,
          what should I do?"). Every proposed move comes with an
          explanation, and you accept, reject, or take pieces. The full
          audit trail (<code>task_events</code>, designed but not yet
          built) is what makes those explanations real.
        </p>
        <p>
          End-of-day reflection is the other side of the same agent: what
          made it onto Today, what got pulled in mid-day, what slipped — a
          structured conversation about how your priorities actually
          moved. Not a chatbot.
        </p>
      </section>

      <footer className="about__footer">
        <div className="about__section-label">Stack</div>
        <p>
          An experiment in treating priority as a first-class data type.
        </p>
      </footer>
    </article>
  );
}
