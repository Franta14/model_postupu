import React, { createContext, useContext, useState, ReactNode } from 'react';

interface FilterContextType {
  selectedTerrains: string[];
  toggleTerrain: (terrain: string) => void;
  clearTerrains: () => void;
  isTerrainSelected: (terrain: string) => boolean;
  activeFilterCount: number;
}

const FilterContext = createContext<FilterContextType | undefined>(undefined);

export const FilterProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [selectedTerrains, setSelectedTerrains] = useState<string[]>([]);

  const toggleTerrain = (terrain: string) => {
    setSelectedTerrains(prev => {
      if (prev.includes(terrain)) {
        return prev.filter(t => t !== terrain);
      } else {
        return [...prev, terrain];
      }
    });
  };

  const clearTerrains = () => {
    setSelectedTerrains([]);
  };

  const isTerrainSelected = (terrain: string) => selectedTerrains.includes(terrain);

  const activeFilterCount = selectedTerrains.length;

  return (
    <FilterContext.Provider
      value={{
        selectedTerrains,
        toggleTerrain,
        clearTerrains,
        isTerrainSelected,
        activeFilterCount,
      }}
    >
      {children}
    </FilterContext.Provider>
  );
};

export const useFilter = () => {
  const context = useContext(FilterContext);
  if (!context) {
    throw new Error('useFilter must be used within a FilterProvider');
  }
  return context;
};
