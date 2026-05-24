/**
 * About / vision page. Honest framing — what Stack actually is, what's
 * shipped, what's still vision. No strawmen, no marketing oversell.
 */
export function AboutPage() {
  return (
    <article className="about">
      <header className="about__hero">
        <div className="about__eyebrow">About Stack</div>
        <h1 className="about__title">An experiment in priority.</h1>
        <p className="about__lede">
          Stack is a to-do app with two opinions. First: the top of every
          stack should be <em>physically larger</em> than the rest — the
          UI should enforce the hierarchy, not let it sit politely in a
          flat list. Second: the data shape of each task should be ready
          for an AI agent before the agent exists.
        </p>
        <p className="about__lede">
          That's mostly it. Stack isn't trying to compete with Things or
          Todoist on polish or feature surface — it's playing a different
          game.
        </p>
      </header>

      <section className="about__section">
        <div className="about__section-label">What's actually different</div>

        <h2 className="about__sub">Visual prominence</h2>
        <p>
          The top task is rendered larger than #2, which is rendered
          larger than #3, and so on. Most to-do apps render every task at
          the same size and let priority be a label or a flag. Stack
          treats size as the signal — you can't hide from what's on top.
        </p>

        <h2 className="about__sub">Stacks as related things</h2>
        <p>
          Other apps treat lists as independent. Stack is built so the
          stacks talk to each other — what's on top of Today should
          influence what's relevant in Reading, in Watching, in Ideas.
          That cross-stack reasoning is mostly latent today; the AI
          agent (below) is what makes it operational.
        </p>

        <h2 className="about__sub">Shareable, ordered backlogs</h2>
        <p>
          Flip any topic stack public and get a URL anyone can open. The
          order matters — visitors see what you're reading next, not just
          a flat library. Goodreads shows your shelf; Stack shows your
          queue.
        </p>
      </section>

      <section className="about__section">
        <div className="about__section-label">How it works today</div>

        <h2 className="about__sub">Daily stacks</h2>
        <p>
          One per day, identified by date. Today, Tomorrow. The top is
          rendered larger than the rest, on purpose. You should feel the
          weight of the one thing that's next.
        </p>

        <h2 className="about__sub">Topic stacks</h2>
        <p>
          Evergreen lists by theme — Reading, Watching, Listening, Buy,
          Ideas, To-Do. These don't have dates. They're the long backlogs
          you pull from. Items live in exactly one stack at a time —
          pulling from Reading into Today is a <em>move</em>, not a
          duplicate.
        </p>

        <h2 className="about__sub">Live timers</h2>
        <p>
          Hit play on the thing you're working on. The timer keeps
          counting even when the tab is closed, because elapsed time is
          computed from the server-side start timestamp — not a frontend
          stopwatch. Mark it done and the time gets archived with the
          task.
        </p>

        <h2 className="about__sub">Per-task context</h2>
        <p>
          Each task carries a link as its primary click target and a
          markdown body for the deeper context. Type once; clicking the
          task opens the link, and the notes stay attached for when you
          need them.
        </p>

        <h2 className="about__sub">Public sharing</h2>
        <p>
          Any topic stack can be flipped public. You get a stable URL;
          anyone can open it without an account. The owner controls
          whether the per-task notes are exposed (off by default — the
          link and the title are always shown, the long-form notes are
          opt-in).
        </p>
      </section>

      <section className="about__section">
        <div className="about__section-label">Where it's going</div>

        <h2 className="about__sub">The AI stack agent</h2>
        <p>
          The agent reads <em>across</em> all your stacks, sees what
          you're focused on right now, and proposes what should move up
          next in the others. Priority as a function of context, not a
          static label.
        </p>
        <p>
          Same logic for context drops ("the deadline moved up", "I'm
          sick tomorrow") and for time windows ("I have two free hours,
          what should I do?"). Every proposed move comes with an
          explanation; you accept, reject, or take pieces. The audit
          trail (<code>task_events</code>, designed but not yet built) is
          what makes those explanations real.
        </p>
        <p>
          End-of-day reflection is the other side of the same agent:
          what made it onto Today, what got pulled in mid-day, what
          slipped. A structured conversation about how your priorities
          actually moved — not a chatbot.
        </p>
        <p>
          The way tasks are structured today is what makes the agent
          possible tomorrow. That's why the data model exists in its
          current shape before any of the agent code does.
        </p>
      </section>

      <footer className="about__footer">
        <div className="about__section-label">Stack</div>
        <p>An experiment in treating priority as a first-class data type.</p>
      </footer>
    </article>
  );
}
