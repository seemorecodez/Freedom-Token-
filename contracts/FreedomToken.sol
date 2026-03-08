// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Pausable.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Address.sol";

/**
 * @title FreedomToken
 * @author FreedomToken Team
 * @notice ERC-20 governance token with AI integration capabilities
 * @dev Implements ERC-20 standard with governance features, burning, pausing,
 *      and AI-assisted proposal creation. Used for DAO voting and staking rewards.
 * @custom:security-contact security@freedomtoken.io
 */
contract FreedomToken is ERC20, ERC20Burnable, ERC20Pausable, AccessControl, ReentrancyGuard {
    using Address for address;

    // ============ Roles ============
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");
    bytes32 public constant BURNER_ROLE = keccak256("BURNER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    bytes32 public constant AI_CONTROLLER_ROLE = keccak256("AI_CONTROLLER_ROLE");
    bytes32 public constant TREASURY_ROLE = keccak256("TREASURY_ROLE");

    // ============ Token Economics ============
    uint256 public constant MAX_SUPPLY = 1_000_000_000 * 10**18; // 1 billion tokens
    uint256 public constant INITIAL_SUPPLY = 100_000_000 * 10**18; // 100 million initial
    
    // ============ Governance ============
    struct Checkpoint {
        uint32 fromBlock;
        uint224 votes;
    }
    
    mapping(address => address) private _delegates;
    mapping(address => Checkpoint[]) private _checkpoints;
    mapping(address => mapping(uint32 => Checkpoint)) private _checkpointsHistory;
    
    // ============ Staking Integration ============
    mapping(address => uint256) public stakedBalance;
    mapping(address => uint256) public stakeStartTime;
    uint256 public constant MIN_STAKE_DURATION = 7 days;
    uint256 public constant MAX_STAKE_DURATION = 365 days;
    
    // ============ AI Integration ============
    struct AIProposal {
        uint256 id;
        address proposer;
        string description;
        string aiLogicExplanation;
        uint256 proposedAt;
        bool executed;
        mapping(address => bool) hasVoted;
        uint256 forVotes;
        uint256 againstVotes;
    }
    
    mapping(uint256 => AIProposal) public aiProposals;
    uint256 public aiProposalCount;
    uint256 public constant AI_PROPOSAL_THRESHOLD = 10000 * 10**18; // 10K tokens
    uint256 public constant AI_VOTING_PERIOD = 7 days;
    
    // ============ Events ============
    event DelegateChanged(address indexed delegator, address indexed fromDelegate, address indexed toDelegate);
    event DelegateVotesChanged(address indexed delegate, uint256 previousBalance, uint256 newBalance);
    event AIProposalCreated(uint256 indexed proposalId, address indexed proposer, string description);
    event AIProposalVoted(uint256 indexed proposalId, address indexed voter, bool support, uint256 votes);
    event AIProposalExecuted(uint256 indexed proposalId);
    event TokensStaked(address indexed user, uint256 amount, uint256 duration);
    event TokensUnstaked(address indexed user, uint256 amount, uint256 reward);
    event EmergencyAction(string action, uint256 timestamp);

    // ============ Errors ============
    error MaxSupplyExceeded(uint256 requested, uint256 max);
    error InvalidAddress(address addr);
    error InsufficientBalance(address account, uint256 requested, uint256 available);
    error StakeLocked(address account, uint256 unlockTime);
    error ProposalThresholdNotMet(address proposer, uint256 balance, uint256 required);
    error ProposalNotFound(uint256 proposalId);
    error VotingClosed(uint256 proposalId, uint256 endTime);
    error AlreadyVoted(uint256 proposalId, address voter);
    error ProposalNotExecutable(uint256 proposalId);
    error TransferWhilePaused(address from, address to);
    error StakingPeriodInvalid(uint256 duration, uint256 min, uint256 max);
    error ZeroAmount();

    // ============ Constructor ============
    /**
     * @notice Initializes the FreedomToken with initial supply distribution
     * @param _treasury Address to receive initial supply and treasury role
     * @param _aiController Address authorized to create AI proposals
     */
    constructor(
        address _treasury,
        address _aiController
    ) ERC20("FreedomToken", "FREE") {
        if (_treasury == address(0)) revert InvalidAddress(_treasury);
        if (_aiController == address(0)) revert InvalidAddress(_aiController);
        
        // Grant admin role to treasury
        _grantRole(DEFAULT_ADMIN_ROLE, _treasury);
        _grantRole(TREASURY_ROLE, _treasury);
        
        // Grant operational roles to treasury initially
        _grantRole(MINTER_ROLE, _treasury);
        _grantRole(BURNER_ROLE, _treasury);
        _grantRole(PAUSER_ROLE, _treasury);
        
        // Grant AI controller role
        _grantRole(AI_CONTROLLER_ROLE, _aiController);
        
        // Mint initial supply to treasury
        _mint(_treasury, INITIAL_SUPPLY);
        
        // Self-delegate treasury for governance
        _delegate(_treasury, _treasury);
    }

    // ============ Minting ============
    /**
     * @notice Mints new tokens to specified address
     * @param to Address to receive minted tokens
     * @param amount Amount of tokens to mint
     * @dev Only callable by addresses with MINTER_ROLE
     * @dev Cannot exceed MAX_SUPPLY
     */
    function mint(address to, uint256 amount) external onlyRole(MINTER_ROLE) nonReentrant {
        if (to == address(0)) revert InvalidAddress(to);
        if (amount == 0) revert ZeroAmount();
        if (totalSupply() + amount > MAX_SUPPLY) {
            revert MaxSupplyExceeded(totalSupply() + amount, MAX_SUPPLY);
        }
        
        _mint(to, amount);
        _moveDelegates(address(0), delegates(to), amount);
    }

    // ============ Burning ============
    /**
     * @notice Burns tokens from specified address
     * @param from Address to burn tokens from
     * @param amount Amount of tokens to burn
     * @dev Only callable by addresses with BURNER_ROLE
     */
    function burnFrom(address from, uint256 amount) public override onlyRole(BURNER_ROLE) nonReentrant {
        if (from == address(0)) revert InvalidAddress(from);
        if (amount == 0) revert ZeroAmount();
        if (balanceOf(from) < amount) {
            revert InsufficientBalance(from, amount, balanceOf(from));
        }
        
        _burn(from, amount);
        _moveDelegates(delegates(from), address(0), amount);
    }

    // ============ Pausability ============
    /**
     * @notice Pauses all token transfers
     * @dev Only callable by PAUSER_ROLE
     */
    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    /**
     * @notice Unpauses token transfers
     * @dev Only callable by DEFAULT_ADMIN_ROLE
     */
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    // ============ Governance - Delegation ============
    /**
     * @notice Returns the current delegated address for an account
     * @param account Address to check delegation for
     * @return Address of the delegate
     */
    function delegates(address account) public view returns (address) {
        return _delegates[account];
    }

    /**
     * @notice Delegate voting power to another address
     * @param delegatee Address to delegate voting power to
     */
    function delegate(address delegatee) external {
        _delegate(msg.sender, delegatee);
    }

    /**
     * @notice Returns current voting power for an address
     * @param account Address to check voting power for
     * @return Current voting power
     */
    function getVotes(address account) public view returns (uint256) {
        uint256 pos = _checkpoints[account].length;
        if (pos == 0) {
            return 0;
        }
        return _checkpoints[account][pos - 1].votes;
    }

    /**
     * @notice Returns voting power at specific block
     * @param account Address to check
     * @param blockNumber Block number to check at
     * @return Voting power at that block
     */
    function getPastVotes(address account, uint256 blockNumber) external view returns (uint256) {
        require(blockNumber < block.number, "FreedomToken: block not yet mined");
        return _checkpointsLookup(_checkpoints[account], blockNumber);
    }

    // ============ AI Proposal System ============
    /**
     * @notice Creates a new AI-assisted proposal
     * @param description Human-readable proposal description
     * @param aiLogicExplanation AI's reasoning for the proposal
     * @return proposalId ID of the created proposal
     */
    function createAIProposal(
        string calldata description,
        string calldata aiLogicExplanation
    ) external onlyRole(AI_CONTROLLER_ROLE) returns (uint256) {
        if (balanceOf(msg.sender) < AI_PROPOSAL_THRESHOLD) {
            revert ProposalThresholdNotMet(msg.sender, balanceOf(msg.sender), AI_PROPOSAL_THRESHOLD);
        }
        
        uint256 proposalId = aiProposalCount++;
        AIProposal storage proposal = aiProposals[proposalId];
        proposal.id = proposalId;
        proposal.proposer = msg.sender;
        proposal.description = description;
        proposal.aiLogicExplanation = aiLogicExplanation;
        proposal.proposedAt = block.timestamp;
        proposal.executed = false;
        
        emit AIProposalCreated(proposalId, msg.sender, description);
        return proposalId;
    }

    /**
     * @notice Vote on an AI proposal
     * @param proposalId ID of proposal to vote on
     * @param support True for yes, false for no
     */
    function voteOnAIProposal(uint256 proposalId, bool support) external {
        AIProposal storage proposal = aiProposals[proposalId];
        
        if (proposal.proposedAt == 0) revert ProposalNotFound(proposalId);
        if (block.timestamp > proposal.proposedAt + AI_VOTING_PERIOD) {
            revert VotingClosed(proposalId, proposal.proposedAt + AI_VOTING_PERIOD);
        }
        if (proposal.hasVoted[msg.sender]) revert AlreadyVoted(proposalId, msg.sender);
        
        uint256 votes = getVotes(msg.sender);
        if (votes == 0) revert InsufficientBalance(msg.sender, 1, 0);
        
        proposal.hasVoted[msg.sender] = true;
        
        if (support) {
            proposal.forVotes += votes;
        } else {
            proposal.againstVotes += votes;
        }
        
        emit AIProposalVoted(proposalId, msg.sender, support, votes);
    }

    /**
     * @notice Execute a passed AI proposal
     * @param proposalId ID of proposal to execute
     */
    function executeAIProposal(uint256 proposalId) external onlyRole(DEFAULT_ADMIN_ROLE) {
        AIProposal storage proposal = aiProposals[proposalId];
        
        if (proposal.proposedAt == 0) revert ProposalNotFound(proposalId);
        if (proposal.executed) revert ProposalNotExecutable(proposalId);
        if (block.timestamp <= proposal.proposedAt + AI_VOTING_PERIOD) {
            revert ProposalNotExecutable(proposalId);
        }
        if (proposal.forVotes <= proposal.againstVotes) {
            revert ProposalNotExecutable(proposalId);
        }
        
        proposal.executed = true;
        emit AIProposalExecuted(proposalId);
        
        // Actual execution logic would be implemented by DAO
    }

    /**
     * @notice Get proposal details
     * @param proposalId ID of proposal
     */
    function getAIProposal(uint256 proposalId) external view returns (
        uint256 id,
        address proposer,
        string memory description,
        string memory aiLogicExplanation,
        uint256 proposedAt,
        bool executed,
        uint256 forVotes,
        uint256 againstVotes
    ) {
        AIProposal storage p = aiProposals[proposalId];
        if (p.proposedAt == 0) revert ProposalNotFound(proposalId);
        
        return (
            p.id,
            p.proposer,
            p.description,
            p.aiLogicExplanation,
            p.proposedAt,
            p.executed,
            p.forVotes,
            p.againstVotes
        );
    }

    // ============ Internal Functions ============
    function _delegate(address delegator, address delegatee) internal {
        address currentDelegate = delegates(delegator);
        uint256 delegatorBalance = balanceOf(delegator);
        _delegates[delegator] = delegatee;
        
        emit DelegateChanged(delegator, currentDelegate, delegatee);
        _moveDelegates(currentDelegate, delegatee, delegatorBalance);
    }

    function _moveDelegates(address from, address to, uint256 amount) internal {
        if (from != to && amount > 0) {
            uint224 amount224 = uint224(amount);
            if (from != address(0)) {
                uint32 fromPos = _addCheckpoint(_checkpoints[from], _subtract, amount224);
                _checkpointsHistory[from][fromPos] = _checkpoints[from][fromPos];
            }
            if (to != address(0)) {
                uint32 toPos = _addCheckpoint(_checkpoints[to], _add, amount224);
                _checkpointsHistory[to][toPos] = _checkpoints[to][toPos];
            }
        }
    }

    function _addCheckpoint(
        Checkpoint[] storage ckpts,
        function(uint224, uint224) pure returns (uint224) op,
        uint224 delta
    ) internal returns (uint32 pos) {
        uint256 oldWeight = _checkpointsLookup(ckpts, block.number);
        uint256 newWeight = op(uint224(oldWeight), delta);
        
        pos = uint32(ckpts.length);
        if (pos > 0 && ckpts[pos - 1].fromBlock == uint32(block.number)) {
            ckpts[pos - 1].votes = uint224(newWeight);
        } else {
            ckpts.push(Checkpoint(uint32(block.number), uint224(newWeight)));
        }
    }

    function _checkpointsLookup(Checkpoint[] storage ckpts, uint256 blockNumber) internal view returns (uint256) {
        uint256 high = ckpts.length;
        uint256 low = 0;
        while (low < high) {
            uint256 mid = (low + high) / 2;
            if (ckpts[mid].fromBlock > blockNumber) {
                high = mid;
            } else {
                low = mid + 1;
            }
        }
        return high == 0 ? 0 : ckpts[high - 1].votes;
    }

    function _add(uint224 a, uint224 b) internal pure returns (uint224) {
        return a + b;
    }

    function _subtract(uint224 a, uint224 b) internal pure returns (uint224) {
        return a - b;
    }

    // ============ Override Functions (OpenZeppelin v5.x Compatible) ============
    /**
     * @notice Override _update to handle governance checkpoints
     * @param from Sender address
     * @param to Recipient address  
     * @param value Amount transferred
     */
    function _update(
        address from,
        address to,
        uint256 value
    ) internal virtual override(ERC20, ERC20Pausable) {
        super._update(from, to, value);
        
        // Update governance checkpoints
        if (from != address(0) && to != address(0)) {
            _moveDelegates(delegates(from), delegates(to), value);
        }
    }

    // ============ Emergency Functions ============
    /**
     * @notice Emergency token recovery for stuck tokens
     * @param token Address of token to recover
     * @param amount Amount to recover
     * @dev Only for tokens accidentally sent to contract
     */
    function emergencyTokenRecovery(
        address token,
        uint256 amount
    ) external onlyRole(DEFAULT_ADMIN_ROLE) nonReentrant {
        require(token != address(this), "FreedomToken: cannot recover FREE");
        IERC20(token).transfer(msg.sender, amount);
        emit EmergencyAction("token_recovery", block.timestamp);
    }

    /**
     * @notice Emergency pause with timelock bypass
     * @dev For critical vulnerabilities only
     */
    function emergencyPause() external {
        require(
            hasRole(DEFAULT_ADMIN_ROLE, msg.sender) || 
            hasRole(PAUSER_ROLE, msg.sender),
            "FreedomToken: must have admin or pauser role"
        );
        _pause();
        emit EmergencyAction("emergency_pause", block.timestamp);
    }
}