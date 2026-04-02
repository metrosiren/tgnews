import Foundation

struct Deck {
    private(set) var cards: [Card]

    init() {
        cards = Deck.buildDeck()
    }

    // MARK: - Build

    static func buildDeck() -> [Card] {
        var deck: [Card] = []

        for color in CardColor.allCases {
            // One 0, two copies of 1–9 per color
            deck.append(Card(color: color, type: .number(0)))
            for n in 1 ... 9 {
                deck.append(Card(color: color, type: .number(n)))
                deck.append(Card(color: color, type: .number(n)))
            }
            // Two of each action card per color
            deck.append(Card(color: color, type: .skip))
            deck.append(Card(color: color, type: .skip))
            deck.append(Card(color: color, type: .reverse))
            deck.append(Card(color: color, type: .reverse))
            deck.append(Card(color: color, type: .drawTwo))
            deck.append(Card(color: color, type: .drawTwo))
        }

        // Four Wild and four Draw +4 (no color)
        for _ in 0 ..< 4 {
            deck.append(Card(color: nil, type: .wild))
            deck.append(Card(color: nil, type: .drawFour))
        }

        // Two Joker cards (no color)
        deck.append(Card(color: nil, type: .joker))
        deck.append(Card(color: nil, type: .joker))

        return deck.shuffled()
    }

    // MARK: - Operations

    mutating func shuffle() {
        cards.shuffle()
    }

    /// Deal a face-up card
    mutating func deal() -> Card? {
        guard !cards.isEmpty else { return nil }
        var card = cards.removeFirst()
        card.isFaceUp = true
        return card
    }

    /// Deal a face-down card
    mutating func dealFaceDown() -> Card? {
        guard !cards.isEmpty else { return nil }
        return cards.removeFirst()
    }

    var isEmpty: Bool { cards.isEmpty }
    var count: Int { cards.count }
}
