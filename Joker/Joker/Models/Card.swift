import Foundation

// MARK: - Card Color

enum CardColor: String, CaseIterable {
    case red, blue, green, yellow

    var displayName: String { rawValue.capitalized }
}

// MARK: - Card Type

enum CardType: Equatable {
    case number(Int)
    case skip
    case reverse
    case drawTwo
    case drawFour
    case wild
    case joker

    var displayName: String {
        switch self {
        case .number(let n): return "\(n)"
        case .skip:          return "Skip"
        case .reverse:       return "Reverse"
        case .drawTwo:       return "+2"
        case .drawFour:      return "+4"
        case .wild:          return "Wild"
        case .joker:         return "Joker"
        }
    }

    var symbolText: String {
        switch self {
        case .number(let n): return "\(n)"
        case .skip:          return "⊘"
        case .reverse:       return "↺"
        case .drawTwo:       return "+2"
        case .drawFour:      return "+4"
        case .wild:          return "★"
        case .joker:         return "🃏"
        }
    }

    var abilityDescription: String {
        switch self {
        case .skip:          return "Dealer skips their next draw"
        case .reverse:       return "Dealer discards a card"
        case .drawTwo:       return "Dealer draws 2 extra cards"
        case .drawFour:      return "Dealer draws 4 extra cards"
        case .wild:          return "Choose this card's value (1–10)"
        case .joker:         return "Wild + any dealer action (once per game!)"
        case .number:        return ""
        }
    }

    /// Base point value before any player assignment
    var basePointValue: Int {
        switch self {
        case .number(let n): return n
        case .skip:          return 5
        case .reverse:       return 5
        case .drawTwo:       return 2
        case .drawFour:      return 4
        case .wild:          return 0
        case .joker:         return 0
        }
    }

    var isAction: Bool {
        switch self {
        case .number: return false
        default:      return true
        }
    }
}

// MARK: - Card

struct Card: Identifiable {
    let id: UUID
    let color: CardColor?   // nil for wild, drawFour, joker
    let type: CardType
    var assignedValue: Int? // player-chosen value for wild/joker
    var isFaceUp: Bool

    init(color: CardColor?, type: CardType, isFaceUp: Bool = false) {
        self.id            = UUID()
        self.color         = color
        self.type          = type
        self.assignedValue = nil
        self.isFaceUp      = isFaceUp
    }

    var pointValue: Int {
        assignedValue ?? type.basePointValue
    }

    var isActionCard: Bool { type.isAction }
    var displayLabel: String { type.displayName }
}
